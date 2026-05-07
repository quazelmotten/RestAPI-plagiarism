"""
Code embedder using F2LLM-v2-80M.

Generates embeddings for:
- Individual functions
- Code snippets
- Entire files (chunked if necessary)
"""

import logging

import numpy as np

from .model_loader import ModelLoader, get_model_loader

logger = logging.getLogger(__name__)

# Chunk size for large files (tokens)
MAX_CHUNK_TOKENS = 400  # Leave room for special tokens


class CodeEmbedder:
    """
    Embedder for code using F2LLM-v2-80M.

    Provides methods to embed functions, snippets, and files.
    Supports int8 quantized inference for memory efficiency.
    """

    def __init__(
        self,
        model_loader: ModelLoader | None = None,
        dimension: int = 256,
    ):
        """
        Initialize embedder.

        Args:
            model_loader: Pre-configured loader (creates default if None)
            dimension: Embedding dimension (MRL support)
        """
        self.loader = model_loader or get_model_loader()
        self.dimension = dimension

    def embed_text(self, code: str, language: str = "python") -> np.ndarray:
        """
        Embed a single code snippet.

        Args:
            code: Source code string
            language: Programming language (for potential preprocessing)

        Returns:
            1D numpy array of shape (dimension,)
        """
        # Note: Removed language prefix as it creates out-of-distribution input
        # F2LLM-v2 was trained on raw code, adding comments can degrade quality

        embedding = self.loader.encode(
            code,
            dimension=self.dimension,
            normalize=True,
        )
        return embedding[0]  # Return 1D array

    def embed_function(
        self,
        func_source: str,
        func_name: str,
        language: str = "python",
    ) -> np.ndarray:
        """
        Embed a single function.

        Args:
            func_source: Function source code
            func_name: Function name (for logging/debugging)
            language: Programming language

        Returns:
            1D numpy array
        """
        logger.debug(f"Embedding function: {func_name}")
        return self.embed_text(func_source, language)

    def embed_file(
        self,
        file_path: str,
        language: str = "python",
        chunk_size: int = MAX_CHUNK_TOKENS,
    ) -> np.ndarray:
        """
        Embed an entire file by chunking if necessary.

        For files that exceed MAX_CHUNK_TOKENS, we chunk and average embeddings.

        Args:
            file_path: Path to source file
            language: Programming language
            chunk_size: Max tokens per chunk

        Returns:
            1D numpy array (averaged if chunked)
        """
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                source = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return np.zeros(self.dimension, dtype=np.float32)

        # Check if we need to chunk
        tokens = self.loader.tokenizer.encode(source)

        if len(tokens) <= chunk_size:
            # File fits in one chunk
            return self.embed_text(source, language)

        # Chunk the file and average embeddings
        logger.info(
            f"File {file_path} exceeds {chunk_size} tokens, chunking..."
        )

        chunks = []
        for i in range(0, len(tokens), chunk_size):
            chunk_tokens = tokens[i : i + chunk_size]
            chunk_text = self.loader.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

        # Embed all chunks
        embeddings = self.loader.encode(
            chunks,
            dimension=self.dimension,
            normalize=True,
        )

        # Average and re-normalize
        avg_embedding = embeddings.mean(axis=0)
        norm = np.linalg.norm(avg_embedding)
        if norm > 0:
            avg_embedding = avg_embedding / norm

        return avg_embedding

    def embed_functions_batch(
        self,
        functions: list[dict],  # Each dict: {"name": str, "source": str, "start_line": int}
        language: str = "python",
    ) -> dict[tuple, np.ndarray]:
        """
        Embed multiple functions in batch for efficiency.

        Args:
            functions: List of function dicts with 'name', 'source', and 'start_line'
            language: Programming language

        Returns:
            Dict mapping (function_name, start_line) to embedding array
        """
        if not functions:
            return {}

        # Prepare batch (no language prefix - model trained on raw code)
        texts = [f["source"] for f in functions]

        # Use (name, start_line) as key to handle duplicate function names
        keys = [(f["name"], f.get("start_line", 0)) for f in functions]

        # Batch encode
        embeddings = self.loader.encode(
            texts,
            dimension=self.dimension,
            normalize=True,
        )

        return dict(zip(keys, embeddings, strict=False))

    def compute_similarity(
        self,
        emb1: np.ndarray,
        emb2: np.ndarray,
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            emb1, emb2: 1D numpy arrays

        Returns:
            Cosine similarity in range [-1, 1]
        """
        # Both embeddings are normalized, so dot product = cosine sim
        return float(np.dot(emb1, emb2))


# Global embedder instance (lazy-loaded)
_global_embedder: CodeEmbedder | None = None


def get_embedder(
    model_name: str = "codefuse-ai/F2LLM-v2-80M",
    use_quantization: bool = True,
    dimension: int = 256,
) -> CodeEmbedder:
    """
    Get or create the global embedder instance.

    Args:
        model_name: HuggingFace model name
        use_quantization: Whether to use int8 quantization
        dimension: Embedding dimension

    Returns:
        CodeEmbedder instance
    """
    global _global_embedder
    if _global_embedder is None:
        loader = get_model_loader(
            model_name=model_name,
            use_quantization=use_quantization,
            device="cpu",
        )
        _global_embedder = CodeEmbedder(loader, dimension=dimension)
    return _global_embedder
