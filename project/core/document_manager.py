from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import shutil
import json
import time
from datetime import datetime
import config
from utils import pdf_to_markdown

_FILE_CACHE_TTL = 30  # seconds

class DocumentManager:

    def __init__(self, rag_system):
        self.rag_system = rag_system
        self.markdown_dir = Path(config.MARKDOWN_DIR)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir = Path(config.DOCUMENTS_DIR)
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.status_path = Path(config.MARKDOWN_DIR).parent / "indexing_status.json"
        self._files_cache: list | None = None
        self._files_cache_at: float = 0.0
        self._cache_lock = threading.Lock()

    def _get_files_cached(self) -> list:
        """Single rglob scan shared by all listing methods, cached for TTL seconds."""
        now = time.monotonic()
        with self._cache_lock:
            if self._files_cache is not None and (now - self._files_cache_at) < _FILE_CACHE_TTL:
                return self._files_cache
        results = []
        if self.markdown_dir.exists():
            for p in sorted(self.markdown_dir.rglob("*.md")):
                try:
                    rel = p.relative_to(self.markdown_dir)
                    state = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "No State"
                    filename = rel.parts[-1].replace(".md", ".pdf")
                    results.append({"state": state, "filename": filename})
                except Exception:
                    continue
        with self._cache_lock:
            self._files_cache = results
            self._files_cache_at = time.monotonic()
        return results

    def _invalidate_cache(self):
        with self._cache_lock:
            self._files_cache = None

    # ── Indexing status (persists to disk so survives page refreshes) ─────────

    def _status_path_for(self, namespace: str | None) -> Path:
        key = (namespace or "root").replace("/", "_").replace(" ", "_")
        return self.status_path.parent / f"indexing_status_{key}.json"

    def _write_status(self, operation: str, namespace: str | None = None,
                      filename: str | None = None, progress: float = 0.0,
                      done: int = 0, total: int = 0):
        try:
            self._status_path_for(namespace).write_text(json.dumps({
                "operation": operation,
                "namespace": namespace,
                "filename": filename,
                "progress": round(progress, 2),
                "done": done,
                "total": total,
                "updated_at": datetime.utcnow().isoformat(),
            }), encoding="utf-8")
        except Exception:
            pass

    def _clear_status(self, namespace: str | None = None):
        """Clear status for a specific namespace, or all status files if namespace is None."""
        try:
            if namespace is not None:
                p = self._status_path_for(namespace)
                if p.exists():
                    p.unlink()
            else:
                for p in self.status_path.parent.glob("indexing_status_*.json"):
                    p.unlink()
                if self.status_path.exists():
                    self.status_path.unlink()
        except Exception:
            pass

    def get_indexing_status(self) -> list[dict] | None:
        """Return list of all active indexing statuses, or None if all idle/stale."""
        statuses = []
        try:
            for p in self.status_path.parent.glob("indexing_status_*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    updated = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
                    if (datetime.utcnow() - updated).total_seconds() > 1800:
                        p.unlink()
                        continue
                    statuses.append(data)
                except Exception:
                    continue
            # Also check legacy single-file status
            if self.status_path.exists():
                try:
                    data = json.loads(self.status_path.read_text(encoding="utf-8"))
                    updated = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
                    if (datetime.utcnow() - updated).total_seconds() <= 1800:
                        statuses.append(data)
                except Exception:
                    pass
        except Exception:
            pass
        return statuses if statuses else None

    def get_namespace_summary(self) -> dict[str, int]:
        """Return {namespace: file_count} from the cached file list."""
        summary: dict[str, int] = defaultdict(int)
        for f in self._get_files_cached():
            summary[f["state"]] += 1
        return dict(sorted(summary.items()))
        
    def add_documents(self, document_paths, state: str | None = None, progress_callback=None):
        if not document_paths:
            return 0, 0

        document_paths = [document_paths] if isinstance(document_paths, str) else document_paths
        document_paths = [p for p in document_paths if p and Path(p).suffix.lower() in [".pdf", ".md"]]

        if not document_paths:
            return 0, 0

        total = len(document_paths)
        target_dir = self.markdown_dir / state if state else self.markdown_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        orig_dir = self.documents_dir / state if state else self.documents_dir
        orig_dir.mkdir(parents=True, exist_ok=True)

        lock = threading.Lock()
        done_count = 0

        def _process_one(doc_path):
            nonlocal done_count
            fname = Path(doc_path).name
            md_path = target_dir / f"{Path(doc_path).stem}.md"

            orig_dest = orig_dir / fname
            if not orig_dest.exists():
                shutil.copy(doc_path, orig_dest)

            try:
                if not md_path.exists():
                    if Path(doc_path).suffix.lower() == ".md":
                        shutil.copy(doc_path, md_path)
                    else:
                        pdf_to_markdown(doc_path, target_dir)

                parent_chunks, child_chunks = self.rag_system.chunker.create_chunks_single(
                    md_path, state=state, original_filename=fname)

                with lock:
                    done_count += 1
                    self._write_status("upload", namespace=state or "No State",
                                       filename=fname, progress=done_count / total,
                                       done=done_count, total=total)
                    if progress_callback:
                        progress_callback(done_count / total, f"[{state or 'No State'}] {fname}")

                if not child_chunks:
                    return None, None
                return parent_chunks, child_chunks

            except Exception as e:
                print(f"Error processing {doc_path}: {e}")
                with lock:
                    done_count += 1
                    self._write_status("upload", namespace=state or "No State",
                                       filename=fname, progress=done_count / total,
                                       done=done_count, total=total)
                return None, None

        # Insert into Qdrant every BATCH_SIZE files so progress is saved incrementally.
        # If the upload is interrupted, already-inserted batches are preserved.
        _BATCH = 100
        collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
        added = 0

        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="doc_upload") as executor:
            for i in range(0, total, _BATCH):
                batch = document_paths[i:i + _BATCH]
                results = list(executor.map(_process_one, batch))

                batch_parent = [c for p, _ in results if p for c in p]
                batch_child  = [c for _, ch in results if ch for c in ch]
                added += sum(1 for p, _ in results if p is not None)
                files_done = min(i + _BATCH, total)

                if batch_child:
                    # Write status before insert so the UI shows progress during the blocking embed+upload step
                    self._write_status("upload", namespace=state or "No State",
                                       filename="indexing batch…",
                                       progress=files_done / total,
                                       done=files_done, total=total)
                    collection.add_documents(batch_child)
                if batch_parent:
                    self.rag_system.parent_store.save_many(batch_parent)

        skipped = total - added
        self._clear_status(namespace=state or "No State")
        self._invalidate_cache()
        return added, skipped
    
    def get_markdown_files(self):
        return [f["filename"] for f in self.get_files_structured()]

    def get_files_structured(self):
        """Return list of {state, filename} dicts for all indexed documents."""
        return list(self._get_files_cached())

    def get_states(self):
        """Return a sorted list of known namespaces (states) derived from the markdown folder layout."""
        seen = set()
        for f in self._get_files_cached():
            if f["state"] != "No State":
                seen.add(f["state"])
        return sorted(seen)

    def reindex_all(self, progress_callback=None):
        """Clear vectors + parent store, then re-chunk and re-index all existing markdown files
        in parallel — one worker thread per namespace. Original PDFs and markdowns are preserved."""
        self.rag_system.parent_store.clear_store()
        self.rag_system.vector_db.delete_collection(self.rag_system.collection_name)
        self.rag_system.vector_db.create_collection(self.rag_system.collection_name)

        # Group markdown files by namespace so each worker owns exactly one state.
        md_files = sorted(self.markdown_dir.rglob("*.md"))
        total = len(md_files)
        if total == 0:
            return 0

        by_namespace: dict[str | None, list[Path]] = defaultdict(list)
        for md_path in md_files:
            rel = md_path.relative_to(self.markdown_dir)
            state = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else None
            by_namespace[state].append(md_path)

        collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
        counter_lock = threading.Lock()
        done = 0
        indexed = 0

        def _process_namespace(state: str | None, paths: list[Path]) -> int:
            nonlocal done, indexed
            count = 0
            ns_label = state or "No State"
            ns_total = len(paths)
            ns_done = 0
            for md_path in paths:
                try:
                    orig_dir = self.documents_dir / state if state else self.documents_dir
                    pdf_name = md_path.stem + ".pdf"
                    original_filename = pdf_name if (orig_dir / pdf_name).exists() else None
                    parent_chunks, child_chunks = self.rag_system.chunker.create_chunks_single(
                        md_path, state=state, original_filename=original_filename
                    )
                    if child_chunks:
                        collection.add_documents(child_chunks)
                        self.rag_system.parent_store.save_many(parent_chunks)
                        count += 1
                except Exception as e:
                    print(f"Error re-indexing {md_path.name} [{state}]: {e}")
                finally:
                    with counter_lock:
                        done += 1
                        ns_done += 1
                        self._write_status("reindex", namespace=ns_label,
                                           filename=md_path.name,
                                           progress=ns_done / ns_total,
                                           done=ns_done, total=ns_total)
                        if progress_callback:
                            progress_callback(done / total, f"[{ns_label}] {md_path.name} ({done}/{total})")
            self._clear_status(namespace=ns_label)
            return count

        n_workers = min(len(by_namespace), 8)
        with ThreadPoolExecutor(max_workers=n_workers, thread_name_prefix="reindex") as executor:
            futures = {
                executor.submit(_process_namespace, state, paths): state
                for state, paths in by_namespace.items()
            }
            for future in as_completed(futures):
                try:
                    indexed += future.result()
                except Exception as e:
                    print(f"Namespace worker failed: {e}")

        self._invalidate_cache()
        return indexed

    def delete_document(self, state: str, filename: str) -> dict:
        """Delete a single document (PDF + MD + vectors + parent chunks).
        state is the namespace (e.g. "NSW"), filename is the original PDF name (e.g. "doc.pdf").
        """
        summary = {"vectors": 0, "parent_chunks": 0, "markdown_files": 0, "original_files": 0}
        qdrant_state = "all" if state == "No State" else state

        # 1. Qdrant vectors (metadata.source == filename)
        summary["vectors"] = self.rag_system.vector_db.delete_by_source(
            self.rag_system.collection_name, filename, qdrant_state
        )

        # 2. Parent store JSON files
        summary["parent_chunks"] = self.rag_system.parent_store.delete_by_source(filename, qdrant_state)

        # 3. Markdown file
        stem = Path(filename).stem
        if state == "No State":
            md_path = self.markdown_dir / f"{stem}.md"
        else:
            md_path = self.markdown_dir / state / f"{stem}.md"
        if md_path.exists():
            md_path.unlink()
            summary["markdown_files"] = 1

        # 4. Original document file
        if state == "No State":
            orig_path = self.documents_dir / filename
        else:
            orig_path = self.documents_dir / state / filename
        if orig_path.exists():
            orig_path.unlink()
            summary["original_files"] = 1

        self._invalidate_cache()
        return summary

    def delete_namespace(self, state: str) -> dict:
        """Delete all data for a specific state/namespace across all storages.
        Returns a summary dict with counts of what was removed."""
        summary = {"vectors": 0, "parent_chunks": 0, "markdown_files": 0, "original_files": 0}

        # 1. Qdrant vectors
        # state stored as "all" when no state was set, but namespace folder is "No State"
        qdrant_state = "all" if state == "No State" else state
        summary["vectors"] = self.rag_system.vector_db.delete_by_state(
            self.rag_system.collection_name, qdrant_state
        )

        # 2. Parent store JSON files
        summary["parent_chunks"] = self.rag_system.parent_store.delete_by_state(qdrant_state)

        # 3. Markdown files
        if state == "No State":
            md_dir = self.markdown_dir
            md_files = [p for p in md_dir.glob("*.md")]
        else:
            md_dir = self.markdown_dir / state
            md_files = list(md_dir.rglob("*.md")) if md_dir.exists() else []
        for p in md_files:
            try:
                p.unlink()
                summary["markdown_files"] += 1
            except Exception:
                pass
        if state != "No State" and md_dir.exists():
            try:
                md_dir.rmdir()  # remove only if now empty
            except Exception:
                pass

        # 4. Original document files (PDFs)
        if state == "No State":
            orig_dir = self.documents_dir
            orig_files = [p for p in orig_dir.iterdir() if p.is_file()] if orig_dir.exists() else []
        else:
            orig_dir = self.documents_dir / state
            orig_files = list(orig_dir.rglob("*")) if orig_dir.exists() else []
            orig_files = [p for p in orig_files if p.is_file()]
        for p in orig_files:
            try:
                p.unlink()
                summary["original_files"] += 1
            except Exception:
                pass
        if state != "No State" and orig_dir.exists():
            try:
                orig_dir.rmdir()
            except Exception:
                pass

        self._invalidate_cache()
        return summary

    def clear_all(self):
        if self.markdown_dir.exists():
            shutil.rmtree(self.markdown_dir)
            self.markdown_dir.mkdir(parents=True, exist_ok=True)
        if self.documents_dir.exists():
            shutil.rmtree(self.documents_dir)
            self.documents_dir.mkdir(parents=True, exist_ok=True)

        self.rag_system.parent_store.clear_store()
        self.rag_system.vector_db.delete_collection(self.rag_system.collection_name)
        self.rag_system.vector_db.create_collection(self.rag_system.collection_name)
        self._invalidate_cache()