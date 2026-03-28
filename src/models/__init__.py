# models package - re-export from shared for backwards compatibility
from shared.models import File, PlagiarismTask, SimilarityResult

__all__ = ["PlagiarismTask", "SimilarityResult", "File"]
