"""
Document chunker — splits loaded documents into vector-DB-ready chunks.

Responsibilities:
  - Receive a list of LangChain Document objects from the loader
  - Split each document into overlapping text chunks using a
    RecursiveCharacterTextSplitter (or similar)
  - Preserve and propagate all source metadata (module_number,
    chapter_number, source_path) onto every derived chunk so the
    chatbot workflow can filter or cite by module/chapter

Planned functions:
  - chunk_documents(
        documents:   list[Document],
        chunk_size:  int = 500,
        chunk_overlap: int = 75,
    ) -> list[Document]
        Returns a flat list of chunk Documents ready for embedding.
"""
