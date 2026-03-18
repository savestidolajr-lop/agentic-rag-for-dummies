from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import shutil
import config
from utils import pdfs_to_markdowns

class DocumentManager:

    def __init__(self, rag_system):
        self.rag_system = rag_system
        self.markdown_dir = Path(config.MARKDOWN_DIR)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir = Path(config.DOCUMENTS_DIR)
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        
    def add_documents(self, document_paths, state: str | None = None, progress_callback=None):
        if not document_paths:
            return 0, 0
            
        document_paths = [document_paths] if isinstance(document_paths, str) else document_paths
        document_paths = [p for p in document_paths if p and Path(p).suffix.lower() in [".pdf", ".md"]]
        
        if not document_paths:
            return 0, 0
            
        added = 0
        skipped = 0
            
        for i, doc_path in enumerate(document_paths):
            if progress_callback:
                progress_callback((i + 1) / len(document_paths), f"Processing {Path(doc_path).name}")
                
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
                        if progress_callback:
                            ns_label = state or "root"
                            progress_callback(done / total, f"[{ns_label}] {md_path.name} ({done}/{total})")
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