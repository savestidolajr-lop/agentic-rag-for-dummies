from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import shutil
import json
from datetime import datetime
import config
from utils import pdfs_to_markdowns

class DocumentManager:

    def __init__(self, rag_system):
        self.rag_system = rag_system
        self.markdown_dir = Path(config.MARKDOWN_DIR)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir = Path(config.DOCUMENTS_DIR)
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.status_path = Path(config.MARKDOWN_DIR).parent / "indexing_status.json"

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
        """Return {namespace: file_count} from the markdown directory."""
        summary: dict[str, int] = defaultdict(int)
        if not self.markdown_dir.exists():
            return {}
        for p in self.markdown_dir.rglob("*.md"):
            try:
                rel = p.relative_to(self.markdown_dir)
                ns = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "No State"
                summary[ns] += 1
            except Exception:
                continue
        return dict(sorted(summary.items()))
        
    def add_documents(self, document_paths, state: str | None = None, progress_callback=None):
        if not document_paths:
            return 0, 0

        document_paths = [document_paths] if isinstance(document_paths, str) else document_paths
        document_paths = [p for p in document_paths if p and Path(p).suffix.lower() in [".pdf", ".md"]]

        if not document_paths:
            return 0, 0

        added = 0
        skipped = 0
        total = len(document_paths)

        for i, doc_path in enumerate(document_paths):
            fname = Path(doc_path).name
            self._write_status("upload", namespace=state or "No State",
                               filename=fname, progress=(i + 1) / total,
                               done=i + 1, total=total)
            if progress_callback:
                progress_callback((i + 1) / total, f"[{state or 'No State'}] {fname}")
                
            doc_name = Path(doc_path).stem
            # Keep documents organized by state/namespace if provided
            target_dir = self.markdown_dir
            if state:
                target_dir = self.markdown_dir / state
                target_dir.mkdir(parents=True, exist_ok=True)

            md_path = target_dir / f"{doc_name}.md"

            # Save original file for later download
            orig_dir = self.documents_dir / state if state else self.documents_dir
            orig_dir.mkdir(parents=True, exist_ok=True)
            orig_dest = orig_dir / Path(doc_path).name
            if not orig_dest.exists():
                shutil.copy(doc_path, orig_dest)

            if md_path.exists():
                skipped += 1
                continue

            try:
                if Path(doc_path).suffix.lower() == ".md":
                    shutil.copy(doc_path, md_path)
                else:
                    pdfs_to_markdowns(str(doc_path), overwrite=False, output_dir=target_dir)
                parent_chunks, child_chunks = self.rag_system.chunker.create_chunks_single(md_path, state=state, original_filename=Path(doc_path).name)
                
                if not child_chunks:
                    skipped += 1
                    continue
                
                collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
                collection.add_documents(child_chunks)
                self.rag_system.parent_store.save_many(parent_chunks)
                
                added += 1

            except Exception as e:
                print(f"Error processing {doc_path}: {e}")
                skipped += 1

        self._clear_status(namespace=state or "No State")
        return added, skipped
    
    def get_markdown_files(self):
        return [f["filename"] for f in self.get_files_structured()]

    def get_files_structured(self):
        """Return list of {state, filename} dicts for all indexed documents."""
        if not self.markdown_dir.exists():
            return []
        results = []
        for p in sorted(self.markdown_dir.rglob("*.md")):
            try:
                rel = p.relative_to(self.markdown_dir)
                state = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "No State"
                filename = rel.parts[-1].replace(".md", ".pdf")
                results.append({"state": state, "filename": filename})
            except Exception:
                continue
        return results

    def get_states(self):
        """Return a sorted list of known namespaces (states) derived from the markdown folder layout."""
        if not self.markdown_dir.exists():
            return []

        states = set()
        for p in self.markdown_dir.rglob("*.md"):
            try:
                rel = p.relative_to(self.markdown_dir)
                if len(rel.parts) > 1:
                    states.add("/".join(rel.parts[:-1]))
            except Exception:
                continue

        return sorted(states)

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

        return indexed

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