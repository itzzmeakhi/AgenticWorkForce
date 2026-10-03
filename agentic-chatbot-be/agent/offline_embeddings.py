import hashlib
import math
import re
from collections import Counter
from typing import List

from chromadb import Documents, EmbeddingFunction, Embeddings

DIM = 256
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


def _hash_index(token: str, dim: int = DIM) -> int:
    h = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(h, 16) % dim


class HashedBagOfWordsEmbedding(EmbeddingFunction):
    """Deterministic, offline, dependency-free text embedding: log-scaled
    term counts hashed into a fixed DIM-length vector, L2-normalized so
    cosine similarity (Chroma's default) behaves sensibly."""

    def name(self) -> str:
        return "hashed-bag-of-words-v1"

    def __call__(self, input: Documents) -> Embeddings:
        vectors = []
        for text in input:
            tokens = _tokenize(text)
            counts = Counter(tokens)
            vec = [0.0] * DIM
            for token, count in counts.items():
                idx = _hash_index(token)
                vec[idx] += 1.0 + math.log(count)
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors
