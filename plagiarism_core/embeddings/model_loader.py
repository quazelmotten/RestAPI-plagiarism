"""
Lightweight model loader for F2LLM-v2-80M with quantization support.

Supports:
- bfloat16 (default, ~160MB)
- int8 quantization (~80MB) 
- Matryoshka Representation Learning (MRL) for flexible dimensions
"""

import logging
from typing import Optional

import numpy as np

# Optional torch import - only needed when actually using the model
try:
    import torch
    from transformers import AutoModel, AutoTokenizer
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    AutoModel = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Model constants
MODEL_NAME = "codefuse-ai/F2LLM-v2-80M"
DEFAULT_DIMENSION = 256  # MRL dimension (can be 64, 128, 256, 384, 768)
MAX_SEQ_LENGTH = 512


class ModelLoader:
    """
    Singleton-style model loader with quantization support.

    Uses lazy loading - model is only loaded when first accessed.
    """

    _instance: Optional["ModelLoader"] = None
    _model: Optional[AutoModel] = None  # type: ignore[assignment]
    _tokenizer: Optional[AutoTokenizer] = None  # type: ignore[assignment]
    _device: object | None = None  # torch.device when available

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        use_quantization: bool = True,
        device: str = "cpu",
        torch_dtype: str = "auto",
    ):
        self.model_name = model_name
        self.use_quantization = use_quantization
        self._device_str = device
        self.torch_dtype = torch_dtype

    def load(self):
        """Load model and tokenizer with quantization if enabled."""
        if not TORCH_AVAILABLE:
            raise RuntimeError("torch is not installed. Install with: pip install torch")

        if self._model is not None:
            return

        logger.info(f"Loading model: {self.model_name}")

        try:
            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
            )

            # Load model with appropriate precision
            if self.use_quantization and self._device_str == "cpu":
                # int8 quantization for CPU (reduces size from ~160MB to ~80MB)
                logger.info("Using int8 quantization for memory efficiency")
                self._model = AutoModel.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                    torch_dtype=torch.float32,  # Load in float32 first for quantization
                )
                # Dynamic quantization for CPU inference
                self._model = torch.quantization.quantize_dynamic(
                    self._model,
                    {torch.nn.Linear},  # Quantize only Linear layers
                    dtype=torch.qint8,
                )
            else:
                # bfloat16 or float16 for GPU/limited precision
                dtype_map = {
                    "bfloat16": torch.bfloat16,
                    "float16": torch.float16,
                    "auto": torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
                }
                dtype = dtype_map.get(self.torch_dtype, torch.bfloat16)
                logger.info(f"Loading model with dtype: {dtype}")
                self._model = AutoModel.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                    torch_dtype=dtype,
                )

            # Move to device
            if self._device_str != "cpu":
                self._model = self._model.to(self._device_str)

            self._model.eval()  # Inference mode
            self._device = torch.device(self.device)

            # Log memory usage
            param_size = sum(p.numel() * p.element_size() for p in self._model.parameters())
            logger.info(f"Model loaded. Approximate size: {param_size / 1024 / 1024:.1f}MB")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    @property
    def model(self) -> AutoModel:
        """Get the loaded model (loads if necessary)."""
        if self._model is None:
            self.load()
        return self._model

    @property
    def tokenizer(self) -> AutoTokenizer:
        """Get the loaded tokenizer (loads if necessary)."""
        if self._tokenizer is None:
            self.load()
        return self._tokenizer

    @property
    def device(self):
        """Get the device model is on."""
        if self._device is None:
            if TORCH_AVAILABLE:
                self._device = torch.device(self._device_str)
            else:
                # Torch not available, just store the string
                self._device = self._device_str
        return self._device

    def encode(
        self,
        texts: list[str] | str,
        dimension: int = DEFAULT_DIMENSION,
        normalize: bool = True,
    ) -> np.ndarray:
        """
        Encode texts into embeddings.

        Args:
            texts: Single text or list of texts
            dimension: Embedding dimension (MRL support: 64, 128, 256, 384, 768)
            normalize: Whether to normalize embeddings to unit length

        Returns:
            numpy array of shape (len(texts), dimension)
        """
        if isinstance(texts, str):
            texts = [texts]

        # Tokenize
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=MAX_SEQ_LENGTH,
            return_tensors="pt",
        ).to(self.device)

        # Generate embeddings
        with torch.no_grad():
            outputs = self.model(**inputs)

            # NOTE: Pooling strategy - currently using EOS token embedding
            # TODO: Verify F2LLM-v2 pooling strategy from model documentation
            # Some models use mean pooling or CLS token instead
            # EOS token is at the end of the sequence
            eos_mask = inputs["input_ids"] == self.tokenizer.eos_token_id
            hidden_states = outputs.last_hidden_state

            # Get EOS token embeddings
            batch_size = hidden_states.shape[0]
            eos_embeddings = []
            for i in range(batch_size):
                eos_indices = eos_mask[i].nonzero(as_tuple=True)[0]
                if len(eos_indices) > 0:
                    eos_idx = eos_indices[-1]  # Last EOS token
                    eos_embeddings.append(hidden_states[i, eos_idx, :])
                else:
                    # Fallback to mean pooling if no EOS
                    eos_embeddings.append(hidden_states[i].mean(dim=0))

            embeddings = torch.stack(eos_embeddings)

            # Apply MRL - truncate to desired dimension
            if dimension < embeddings.shape[1]:
                embeddings = embeddings[:, :dimension]

            # Normalize if requested
            if normalize:
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        return embeddings.cpu().numpy()


# Global loader instance (lazy-loaded)
_global_loader: ModelLoader | None = None


def get_model_loader(
    model_name: str = MODEL_NAME,
    use_quantization: bool = True,
    device: str = "cpu",
) -> ModelLoader:
    """Get or create the global model loader."""
    global _global_loader
    if _global_loader is None:
        _global_loader = ModelLoader(
            model_name=model_name,
            use_quantization=use_quantization,
            device=device,
        )
    return _global_loader
