"""
All API routes for the RAG chat application.

Initialise with:
    from api.routes import router, init_routes
    init_routes(chat_interface_instance, doc_manager_instance, rag_system_instance)
    app.include_router(router)
"""

import asyncio
import re
import tempfile
import shutil
import time
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

import config
from core import admin_config
from rag_agent.prompts import get_orchestrator_prompt, get_aggregation_prompt, get_fallback_response_prompt
from api.deps import get_current_user, get_current_user_upload

# ── Module-level state populated by init_routes() ────────────────────────────

_state: dict = {
    "chat_interface": None,
    "doc_manager": None,
    "rag_system": None,
}

_chat_executor   = ThreadPoolExecutor(max_workers=8, thread_name_prefix="api_chat")
_upload_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="api_upload")

router = APIRouter()


def init_routes(chat_interface, doc_manager, rag_system) -> None:
    """Call once at startup to inject the shared service instances."""
    _state["chat_interface"] = chat_interface
    _state["doc_manager"] = doc_manager
    _state["rag_system"] = rag_system


# ── Tag parsing helpers ───────────────────────────────────────────────────────

_CITED_RE = re.compile(r'\[CITED_DOCUMENTS\](.*?)\[/CITED_DOCUMENTS\]', re.DOTALL | re.IGNORECASE)
_OPTIONS_RE = re.compile(r'\[OPTIONS:\s*([^\]]+)\]', re.IGNORECASE)


def _parse_cited_documents(text: str) -> list[str]:
    """Extract filenames from [CITED_DOCUMENTS]["file.pdf", "file2.pdf"][/CITED_DOCUMENTS] tags."""
    matches = _CITED_RE.findall(text)
    docs = []
    for block in matches:
        # Pull every double-quoted string from the block (handles comma-separated lists)
        file_matches = re.findall(r'"([^"]+)"', block)
        docs.extend(f.strip() for f in file_matches if f.strip())
    return list(dict.fromkeys(docs))  # deduplicate, preserving order


def _parse_options(text: str) -> list[str]:
    """Extract options from [OPTIONS: A | B | C] tag."""
    m = _OPTIONS_RE.search(text)
    if not m:
        return []
    return [o.strip() for o in m.group(1).split("|") if o.strip()]


def _strip_tags(text: str) -> str:
    """Remove [CITED_DOCUMENTS]...[/CITED_DOCUMENTS] and [OPTIONS:...] from text."""
    text = _CITED_RE.sub("", text)
    text = _OPTIONS_RE.sub("", text)
    return text.strip()


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse_event(event: str, data: str) -> str:
    """Format a named SSE event."""
    import json as _json
    return f"event: {event}\ndata: {data}\n\n"


# ── Request / response models ─────────────────────────────────────────────────

class ChatStreamRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    state_filter: Optional[str] = None
    model: Optional[str] = None
    user_name: Optional[str] = None


class StopRequest(BaseModel):
    session_id: str


class EvaluateRequest(BaseModel):
    question: str
    answer: str


class CreateSessionRequest(BaseModel):
    pass


class PatchConfigRequest(BaseModel):
    model: str


class SaveAISettingsRequest(BaseModel):
    temperature: float
    max_tool_calls: int
    orchestrator_prompt: str = ""
    aggregation_prompt: str = ""
    fallback_response_prompt: str = ""


class AddNamespaceRequest(BaseModel):
    name: str


# Australian state/territory codes that ship with the app — cannot be deleted
DEFAULT_NAMESPACES: list[str] = ["NSW", "VIC", "QLD", "SA", "NT", "WA", "TAS", "ACT"]


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/api/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    ci = _state["chat_interface"]
    sessions = ci.get_sessions(user_id=user["uid"])
    return {"sessions": sessions}


@router.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, user: dict = Depends(get_current_user)):
    ci = _state["chat_interface"]
    messages = ci.get_session_messages(session_id)
    processed = []
    for m in messages:
        content = m["content"]
        cited: list[str] = []
        if m["role"] == "assistant":
            cited = _parse_cited_documents(content)
            content = _strip_tags(content)
        processed.append({**m, "content": content, "cited_documents": cited})
    return {"messages": processed}


@router.post("/api/sessions")
async def create_session(user: dict = Depends(get_current_user)):
    ci = _state["chat_interface"]
    session_id = ci.create_new_session(user_id=user["uid"])
    return {"session_id": session_id}


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    ci = _state["chat_interface"]
    ci.delete_session(session_id)
    return {"ok": True}


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.post("/api/chat/stream")
async def chat_stream(body: ChatStreamRequest, user: dict = Depends(get_current_user)):
    """
    SSE endpoint that streams the RAG response.

    Emits named events:
      - activity  {"steps": [...]}
      - token     {"text": "...", "session_id": "..."}   (full accumulated text)
      - done      {"session_id": "...", "cited_documents": [...], "options": [...], "title": "..."}
      - error     {"message": "..."}
    """
    import json as _json

    ci = _state["chat_interface"]
    rag = _state["rag_system"]

    # Optionally switch model before streaming
    if body.model and body.model in config.AVAILABLE_MODELS:
        provider, model_id = config.AVAILABLE_MODELS[body.model]
        try:
            rag.switch_model(provider, model_id)
        except Exception:
            pass  # non-fatal — carry on with current model

    # We bridge the sync generator into async via a Queue + thread pool
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    _SENTINEL = object()

    _user_name = (body.user_name or "").strip()

    def _run_generator():
        try:
            for partial_text, session_id, activity_steps, is_narration in ci.stream_response(
                body.message,
                session_id=body.session_id,
                state_filter=body.state_filter,
                user_id=user["uid"],
                user_name=_user_name,
            ):
                kind = "narration" if is_narration else "chunk"
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    (kind, partial_text, session_id, activity_steps),
                )
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc), None, []))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    loop.run_in_executor(_chat_executor, _run_generator)

    async def _generate():
        last_session_id = body.session_id
        last_steps: list = []
        final_text = ""

        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if item is _SENTINEL:
                    break

                kind, text, session_id, activity_steps = item

                if kind == "error":
                    yield _sse_event("error", _json.dumps({"message": text}))
                    return

                if session_id:
                    last_session_id = session_id

                # Emit activity if steps changed
                if activity_steps != last_steps:
                    last_steps = activity_steps
                    yield _sse_event("activity", _json.dumps({"steps": activity_steps}))

                # Emit narration or token with cleaned text (tags stripped)
                if text:
                    clean_text = _strip_tags(text)
                    if kind == "narration":
                        yield _sse_event("narration", _json.dumps({"text": clean_text}))
                    else:
                        final_text = text
                        yield _sse_event(
                            "token",
                            _json.dumps({"text": clean_text, "session_id": last_session_id}),
                        )

            # Emit done with parsed structured data
            cited = _parse_cited_documents(final_text)
            options = _parse_options(final_text)

            # Fetch current session title
            title = ""
            if last_session_id:
                sessions = ci.get_sessions(user_id=user["uid"])
                for s in sessions:
                    if s.get("session_id") == last_session_id:
                        title = s.get("title", "")
                        break

            yield _sse_event(
                "done",
                _json.dumps({
                    "session_id": last_session_id,
                    "cited_documents": cited,
                    "options": options,
                    "title": title,
                }),
            )

        except asyncio.CancelledError:
            # Client disconnected — stop the session if we have an id
            if last_session_id:
                try:
                    ci.stop_session(last_session_id)
                except Exception:
                    pass
            raise

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/api/chat/stop")
async def chat_stop(body: StopRequest, user: dict = Depends(get_current_user)):
    ci = _state["chat_interface"]
    ci.stop_session(body.session_id)
    return {"ok": True}


@router.post("/api/chat/evaluate")
async def chat_evaluate(body: EvaluateRequest, user: dict = Depends(get_current_user)):
    ci = _state["chat_interface"]
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _upload_executor,
        lambda: ci.evaluate_response(body.question, body.answer),
    )
    return {"result": result}


# ── Documents ─────────────────────────────────────────────────────────────────

@router.get("/api/documents")
async def list_documents(
    state: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 0,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    dm = _state["doc_manager"]
    all_files = dm.get_files_structured()
    states = dm.get_states()

    # Filter by state
    if state:
        all_files = [f for f in all_files if f.get("state") == state]

    # Filter by search term
    if search:
        search_lower = search.lower()
        all_files = [f for f in all_files if search_lower in f.get("filename", "").lower()]

    total = len(all_files)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = page * page_size
    paginated = all_files[start: start + page_size]

    return {
        "files": paginated,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "states": states,
    }


# ── Download ──────────────────────────────────────────────────────────────

@router.get("/api/download/file/{filename:path}")
async def download_file_by_name(filename: str, user: dict = Depends(get_current_user)):
    """Find a document by filename across all state subdirectories."""
    import pathlib
    docs_root = pathlib.Path(config.DOCUMENTS_DIR)
    # Search all subdirectories (state namespaces) for the file
    for candidate in [docs_root / filename, *docs_root.rglob(filename)]:
        if candidate.is_file():
            return FileResponse(str(candidate), filename=filename, media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="File not found")


@router.get("/api/download/{state}/{filename:path}")
async def download_file(state: str, filename: str, user: dict = Depends(get_current_user)):
    dm = _state["doc_manager"]
    file_path = os.path.join(config.DOCUMENTS_DIR, state, filename)
    if not os.path.isfile(file_path):
        # Try root documents dir (No State)
        file_path = os.path.join(config.DOCUMENTS_DIR, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename, media_type="application/octet-stream")


@router.delete("/api/documents/{state}/{filename:path}")
async def delete_document(state: str, filename: str, user: dict = Depends(get_current_user)):
    dm = _state["doc_manager"]
    loop = asyncio.get_event_loop()
    summary = await loop.run_in_executor(
        _upload_executor,
        lambda: dm.delete_document(state, filename),
    )
    return {"ok": True, "summary": summary}


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.post("/api/admin/upload")
async def admin_upload(
    files: list[UploadFile] = File(...),
    state: str = Form(""),
    user: dict = Depends(get_current_user),
):
    dm = _state["doc_manager"]

    # Save to a persistent staging dir (not a TemporaryDirectory context manager)
    # so indexing survives even if the client disconnects or refreshes the page.
    staging_dir = Path(tempfile.gettempdir()) / f"rag_upload_{int(time.time() * 1000)}"
    staging_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for upload in files:
        dest = staging_dir / (upload.filename or f"file_{len(saved_paths)}")
        # Fix: stream from starlette's spooled file instead of loading entire file into RAM
        with dest.open("wb") as f:
            shutil.copyfileobj(upload.file, f)
        saved_paths.append(str(dest))

    queued = len(saved_paths)

    # Fire-and-forget: index in the background so the HTTP response returns immediately.
    # The client polls GET /api/admin/stats for live progress bars.
    def _process():
        try:
            dm.add_documents(saved_paths, state=state or None, progress_callback=None)
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    _upload_executor.submit(_process)

    return {"status": "processing", "queued": queued}


@router.post("/api/admin/upload-zip")
async def admin_upload_zip(
    file: UploadFile = File(...),
    state: str = Form(""),
    user: dict = Depends(get_current_user_upload),
):
    dm = _state["doc_manager"]

    staging_dir = Path(tempfile.gettempdir()) / f"rag_upload_{int(time.time() * 1000)}"
    staging_dir.mkdir(parents=True, exist_ok=True)
    zip_path = staging_dir / "upload.zip"

    # Stream ZIP to disk — no full-file RAM load
    with zip_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Scan ZIP headers to count valid files (fast — no extraction yet)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            valid_members = [
                m for m in zf.infolist()
                if not m.is_dir()
                and "__MACOSX" not in m.filename
                and not Path(m.filename).name.startswith(".")
                and Path(m.filename).suffix.lower() in [".pdf", ".md"]
            ]
        queued = len(valid_members)
    except zipfile.BadZipFile:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Invalid ZIP file")

    def _process():
        try:
            extract_dir = staging_dir / "extracted"
            extract_dir.mkdir()
            with zipfile.ZipFile(zip_path) as zf:
                for member in zf.infolist():
                    if (member.is_dir()
                            or "__MACOSX" in member.filename
                            or Path(member.filename).name.startswith(".")
                            or Path(member.filename).suffix.lower() not in [".pdf", ".md"]):
                        continue
                    # Flatten to single directory but avoid overwriting duplicates:
                    # if two entries share a basename, prefix with parent folder name.
                    p = Path(member.filename)
                    basename = p.name
                    dest = extract_dir / basename
                    if dest.exists() and p.parent.name:
                        basename = f"{p.parent.name}__{p.name}"
                        dest = extract_dir / basename
                    # Final guard with numeric suffix for any remaining collision
                    counter = 1
                    while dest.exists():
                        dest = extract_dir / f"{p.stem}__{counter}{p.suffix}"
                        counter += 1
                    with zf.open(member) as src, dest.open("wb") as dst:
                        shutil.copyfileobj(src, dst)

            extracted = [str(p) for p in extract_dir.iterdir() if p.is_file()]
            dm.add_documents(extracted, state=state or None, progress_callback=None)
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    _upload_executor.submit(_process)

    return {"status": "processing", "queued": queued}


@router.get("/api/admin/stats")
async def admin_stats(user: dict = Depends(get_current_user)):
    dm = _state["doc_manager"]
    rag = _state["rag_system"]

    loop = asyncio.get_event_loop()

    namespaces, indexing_status, health = await asyncio.gather(
        loop.run_in_executor(None, dm.get_namespace_summary),
        loop.run_in_executor(None, dm.get_indexing_status),
        loop.run_in_executor(None, lambda: rag.get_health(refresh=False)),
    )

    # Count vectors per namespace from Qdrant
    def _count_vectors():
        counts = {}
        for ns in namespaces:
            qdrant_state = "all" if ns == "No State" else ns
            counts[ns] = rag.vector_db.count_by_state(rag.collection_name, qdrant_state)
        return counts

    vector_counts = await loop.run_in_executor(None, _count_vectors)

    return {
        "namespaces": namespaces,
        "vector_counts": vector_counts,
        "indexing_status": indexing_status or [],
        "health": health,
    }


@router.get("/api/admin/config")
async def admin_get_config(user: dict = Depends(get_current_user)):
    rag = _state["rag_system"]
    available = list(config.AVAILABLE_MODELS.keys())
    current_provider = getattr(rag, "_active_provider", config.LLM_PROVIDER)
    current_model = getattr(rag, "_active_model", "")

    # Find the display name for the currently active model
    current_display = ""
    for name, (provider, model_id) in config.AVAILABLE_MODELS.items():
        if provider == current_provider and model_id == current_model:
            current_display = name
            break

    return {
        "available_models": available,
        "current_model": current_display,
        "current_provider": current_provider,
    }


@router.patch("/api/admin/config")
async def admin_patch_config(body: PatchConfigRequest, user: dict = Depends(get_current_user)):
    rag = _state["rag_system"]

    if body.model not in config.AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {body.model!r}")

    provider, model_id = config.AVAILABLE_MODELS[body.model]

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        _upload_executor,
        lambda: rag.switch_model(provider, model_id),
    )

    return {"ok": True}


@router.delete("/api/admin/namespace/{state}")
async def admin_delete_namespace(state: str, user: dict = Depends(get_current_user)):
    dm = _state["doc_manager"]
    loop = asyncio.get_event_loop()
    summary = await loop.run_in_executor(
        _upload_executor,
        lambda: dm.delete_namespace(state),
    )
    return {"ok": True, "summary": summary}


@router.delete("/api/admin/all")
async def admin_delete_all(user: dict = Depends(get_current_user)):
    dm = _state["doc_manager"]
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_upload_executor, dm.clear_all)
    return {"ok": True}


@router.post("/api/admin/reindex")
async def admin_reindex(user: dict = Depends(get_current_user)):
    dm = _state["doc_manager"]
    loop = asyncio.get_event_loop()
    indexed = await loop.run_in_executor(
        _upload_executor,
        lambda: dm.reindex_all(),
    )
    return {"ok": True, "indexed": indexed}


@router.get("/api/admin/ai-settings")
async def admin_get_ai_settings(user: dict = Depends(get_current_user)):
    overrides = admin_config.get_all()
    default_orch = get_orchestrator_prompt()
    default_agg = get_aggregation_prompt()
    default_fallback = get_fallback_response_prompt()
    return {
        "temperature": admin_config.get("temperature", config.LLM_TEMPERATURE),
        "max_tool_calls": admin_config.get("max_tool_calls", config.MAX_TOOL_CALLS),
        # Return active prompt (override if set, else built-in default)
        "orchestrator_prompt": overrides.get("orchestrator_prompt") or default_orch,
        "aggregation_prompt": overrides.get("aggregation_prompt") or default_agg,
        "fallback_response_prompt": overrides.get("fallback_response_prompt") or default_fallback,
        "defaults": {
            "temperature": config.LLM_TEMPERATURE,
            "max_tool_calls": config.MAX_TOOL_CALLS,
            "orchestrator_prompt": default_orch,
            "aggregation_prompt": default_agg,
            "fallback_response_prompt": default_fallback,
        },
    }


@router.post("/api/admin/ai-settings")
async def admin_save_ai_settings(body: SaveAISettingsRequest, user: dict = Depends(get_current_user)):
    rag = _state["rag_system"]
    admin_config.save({
        "temperature": body.temperature,
        "max_tool_calls": body.max_tool_calls,
        "orchestrator_prompt": body.orchestrator_prompt.strip(),
        "aggregation_prompt": body.aggregation_prompt.strip(),
        "fallback_response_prompt": body.fallback_response_prompt.strip(),
    })
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_upload_executor, rag.apply_settings)
    return {"ok": True}


@router.post("/api/admin/ai-settings/reset")
async def admin_reset_ai_settings(user: dict = Depends(get_current_user)):
    rag = _state["rag_system"]
    admin_config.reset()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_upload_executor, rag.apply_settings)
    return {
        "ok": True,
        "temperature": config.LLM_TEMPERATURE,
        "max_tool_calls": config.MAX_TOOL_CALLS,
    }


# ── Namespace management ───────────────────────────────────────────────────────

def _get_custom_namespaces() -> list[str]:
    return admin_config.get_all().get("custom_namespaces") or []


@router.get("/api/admin/namespaces")
async def list_namespaces(user: dict = Depends(get_current_user)):
    dm = _state["doc_manager"]
    custom = _get_custom_namespaces()
    # Also include any namespace that exists on disk (e.g. uploaded without being
    # explicitly registered in the custom list)
    fs_states = dm.get_states() if dm else []
    all_ns = list(DEFAULT_NAMESPACES)
    for ns in custom + fs_states:
        if ns not in all_ns:
            all_ns.append(ns)
    return {
        "default": DEFAULT_NAMESPACES,
        "custom": custom,
        "all": all_ns,
    }


@router.post("/api/admin/namespaces")
async def add_namespace(body: AddNamespaceRequest, user: dict = Depends(get_current_user)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Namespace name cannot be empty")
    if name in DEFAULT_NAMESPACES:
        raise HTTPException(status_code=400, detail="That is a built-in namespace")
    custom = _get_custom_namespaces()
    if name in custom:
        raise HTTPException(status_code=409, detail="Namespace already exists")
    custom.append(name)
    admin_config.save({"custom_namespaces": custom})
    return {"ok": True, "name": name}


@router.delete("/api/admin/namespaces/{name}")
async def delete_namespace(name: str, user: dict = Depends(get_current_user)):
    if name in DEFAULT_NAMESPACES:
        raise HTTPException(status_code=403, detail="Built-in namespaces cannot be deleted")
    custom = _get_custom_namespaces()
    if name not in custom:
        raise HTTPException(status_code=404, detail="Namespace not found")
    custom.remove(name)
    admin_config.save({"custom_namespaces": custom})
    return {"ok": True}
