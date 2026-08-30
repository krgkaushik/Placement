"""Embedding helpers for semantic placement matching."""

from functools import lru_cache
import math


@lru_cache(maxsize=1)
def _get_embedding_model():
    """Load the embedding model once, on first use."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError(
            "sentence-transformers is required for semantic matching. "
            "Install it with: pip install sentence-transformers"
        ) from error

    return SentenceTransformer("all-MiniLM-L6-v2")


def generate_embedding(text):
    """Return an all-MiniLM-L6-v2 embedding as a list of floats."""
    normalized_text = str(text or "").strip()
    if not normalized_text:
        return []

    embedding = _get_embedding_model().encode(normalized_text)
    return [float(value) for value in embedding.tolist()]


def cosine_similarity(first_vector, second_vector):
    """Return cosine similarity for two equal-length numeric vectors."""
    if not first_vector or not second_vector or len(first_vector) != len(second_vector):
        return None

    first_norm = math.sqrt(sum(value * value for value in first_vector))
    second_norm = math.sqrt(sum(value * value for value in second_vector))
    if not first_norm or not second_norm:
        return None

    return sum(
        first_value * second_value
        for first_value, second_value in zip(first_vector, second_vector)
    ) / (first_norm * second_norm)
