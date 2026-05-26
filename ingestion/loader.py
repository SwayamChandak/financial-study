"""
Document loader — reads raw study material from disk.

Responsibilities:
  - Accept a source path (directory or single file)
  - Support PDF, DOCX, and plain-text formats
  - Tag each loaded document with metadata:
      module_number  (int)  — derived from folder / filename convention
      chapter_number (int)  — derived from folder / filename convention
      source_path    (str)  — original file path for traceability

Planned functions:
  - load_documents(source_dir: str) -> list[Document]
      Walks source_dir, loads every supported file, and returns a list
      of LangChain Document objects with the metadata above attached.
  - _load_pdf(path: str)    -> list[Document]
  - _load_docx(path: str)   -> list[Document]
  - _load_txt(path: str)    -> list[Document]
"""
