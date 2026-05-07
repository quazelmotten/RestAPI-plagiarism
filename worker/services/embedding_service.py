"""
Embedding service - generates and caches code embeddings.

Integrates F2LLM-v2-80M to generate embeddings for:
- Entire files (for overall similarity)
- Individual functions (for function-level matching)
"""

import logging

import numpy as np
from plagiarism_core.embeddings import CodeEmbedder, EmbeddingCache, get_embedder

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and caching code embeddings."""

    def __init__(
        self,
        embedding_cache: EmbeddingCache | None = None,
        dimension: int = 256,
        use_quantization: bool = True,
    ):
        """
        Initialize embedding service.

        Args:
            embedding_cache: Cache for storing embeddings (Redis + DB)
            dimension: Embedding dimension (MRL support: 64, 128, 256, 384, 768)
            use_quantization: Use int8 quantization for memory efficiency
        """
        self.cache = embedding_cache
        self.dimension = dimension
        self.use_quantization = use_quantization
        self._embedder: CodeEmbedder | None = None

    @property
    def embedder(self) -> CodeEmbedder:
        """Lazy-load the embedder."""
        if self._embedder is None:
            self._embedder = get_embedder(
                dimension=self.dimension,
                use_quantization=self.use_quantization,
            )
        return self._embedder

    def ensure_embedded(
        self,
        file_info: dict,
        language: str,
    ) -> np.ndarray | None:
        """
        Ensure file has embedding cached. Generate if missing.

        Args:
            file_info: Dict with 'file_hash', 'file_path'
            language: Programming language

        Returns:
            Numpy array embedding or None if failed
        """
        file_hash = file_info.get("file_hash") or file_info.get("hash")
        file_path = file_info.get("file_path") or file_info.get("path")

        if not file_hash or not file_path:
            logger.error("Invalid file info: missing hash or path")
            return None

        # Check cache first
        if self.cache:
            cached = self.cache.get(file_hash)
            if cached is not None:
                logger.debug(f"Embedding from cache for {file_hash[:16]}...")
                return cached

        # Generate embedding
        try:
            logger.info(f"Generating embedding for {file_path}")
            embedding = self.embedder.embed_file(file_path, language)

            # Cache the embedding
            if self.cache:
                self.cache.set(file_hash, embedding)

            logger.info(
                f"Generated and cached embedding ({len(embedding)} dims) "
                f"for {file_hash[:16]}..."
            )
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding for {file_path}: {e}")
            return None

    def get_embedding(self, file_hash: str) -> np.ndarray | None:
        """Get embedding from cache if available."""
        if not self.cache:
            return None
        return self.cache.get(file_hash)

    def get_embeddings_batch(
        self, file_hashes: list[str]
    ) -> dict[str, np.ndarray]:
        """Get multiple embeddings at once."""
        if not self.cache:
            return {}
        return self.cache.get_batch(file_hashes)

    def compute_similarity(
        self, emb1: np.ndarray, emb2: np.ndarray
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        return self.embedder.compute_similarity(emb1, emb2)

    def generate_function_embeddings(
        self, file_path: str, language: str
    ) -> dict[str, np.ndarray]:
        """
        Generate embeddings for each function in a file.

        Returns:
            Dict mapping function name to embedding
        """
        try:
            from plagiarism_core.detection.ast_helpers import _extract_functions
            from plagiarism_core.fingerprinting.parser import parse_file_once

            tree, source_bytes = parse_file_once(file_path, language)
            functions = _extract_functions(tree.root_node, source_bytes, language)

            if not functions:
                return {}

            # Prepare function sources
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            func_data = []
            for func in functions:
                start = func["start_line"]
                end = func["end_line"]
                source = "".join(lines[start : end + 1])
                func_data.append({"name": func["name"], "source": source, "start_line": start})

            # Batch embed
            return self.embedder.embed_functions_batch(func_data, language)

        except Exception as e:
            logger.error(f"Failed to generate function embeddings for {file_path}: {e}")
            return {}

    def unload_model(self):
        """Unload the model to free memory (if needed)."""
        import plagiarism_core.embeddings.embedder as embedder_module

        if embedder_module._global_embedder is not None:
            # Delete the model to free memory
            import torch

            if hasattr(embedder_module._global_embedder.loader, "_model"):
                model = embedder_module._global_embedder.loader._model
                if model is not None:
                    del model
                embedder_module._global_embedder.loader._model = None

            if hasattr(embedder_module._global_embedder.loader, "_tokenizer"):
                embedder_module._global_embedder.loader._tokenizer = None

            embedder_module._global_embedder = None

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info("Embedding model unloaded")
