"""
Embeddings module for hybrid AST+embedding plagiarism detection.

Provides lightweight F2LLM-v2-80M integration with int8 quantization
for memory-efficient code embeddings.
"""

from .cache import EmbeddingCache
from .embedder import CodeEmbedder, get_embedder
from .model_loader import ModelLoader

__all__ = [
    "ModelLoader",
    "CodeEmbedder",
    "get_embedder",
    "EmbeddingCache",
    "cosine_similarity",
]
