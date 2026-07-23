from hashlib import sha256


class DeterministicEmbeddingProvider:
    """Local placeholder embedding provider.

    This is deterministic so Qdrant integration can be tested in Phase 1 without
    binding the platform to a paid embedding provider. Replace with a real provider
    behind the same interface for production retrieval quality.
    """

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        seed = sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        counter = 0
        while len(values) < self.dimension:
            digest = sha256(seed + counter.to_bytes(4, "big")).digest()
            values.extend(((byte / 127.5) - 1.0) for byte in digest)
            counter += 1
        return values[: self.dimension]

