"""
Embedder — returns a ready-to-use HuggingFace Embeddings instance.

Model : sentence-transformers/all-MiniLM-L12-v2
Dim   : 384
Norm  : L2-normalized (enables cosine similarity via dot product)

The model is downloaded from HuggingFace Hub on first call and cached
locally by the sentence-transformers library.
"""

from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings

from config.settings import settings


def get_embedder() -> HuggingFaceEmbeddings:
    """
    Instantiate and return a HuggingFaceEmbeddings object configured with
    the model and normalization options from application settings.
    """
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model_name,
        encode_kwargs={"normalize_embeddings": settings.embedding_normalize},
    )
