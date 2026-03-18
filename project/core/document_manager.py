from pathlib import Path
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