"""In-memory recognition gallery kept in sync with SQLite.

Embeddings never leave the process: the API only exposes member metadata.
Multiple embeddings per member are supported (several enrolment photos), and a
member's score is the best match across their embeddings.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from ..core.logging import get_logger
from ..db import database as db

log = get_logger("gallery")


@dataclass
class MatchResult:
    accepted: bool
    member_id: str | None = None
    name: str | None = None
    similarity: float = 0.0
    second_similarity: float = 0.0
    margin: float = 0.0
    reason: str = "no_candidates"  # accepted | below_threshold | ambiguous | no_candidates

    def as_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "member_id": self.member_id,
            "name": self.name,
            "similarity": round(float(self.similarity), 4),
            "margin": round(float(self.margin), 4),
            "reason": self.reason,
        }


class FaceGallery:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._matrix = np.zeros((0, 128), dtype=np.float32)
        self._member_ids: list[str] = []
        self._names: dict[str, str] = {}
        self._dim = 128

    # -- lifecycle ---------------------------------------------------------
    def load_from_db(self) -> None:
        rows = db.query_all(
            """SELECT e.member_id, e.vector, e.dim, m.name
               FROM embeddings e JOIN members m ON m.id = e.member_id
               ORDER BY e.id"""
        )
        vectors: list[np.ndarray] = []
        member_ids: list[str] = []
        names: dict[str, str] = {}
        for row in rows:
            try:
                vec = np.frombuffer(row["vector"], dtype=np.float32).copy()
            except (TypeError, ValueError):
                log.warning("skipping unreadable embedding for member %s", row["member_id"])
                continue
            if vec.size != row["dim"] or vec.size != self._dim or not np.all(np.isfinite(vec)):
                log.warning("skipping malformed embedding for member %s (dim=%s)", row["member_id"], vec.size)
                continue
            norm = float(np.linalg.norm(vec))
            if not np.isfinite(norm) or norm < 1e-9:
                continue
            vectors.append(vec / norm)
            member_ids.append(row["member_id"])
            names[row["member_id"]] = row["name"]
        with self._lock:
            self._member_ids = member_ids
            self._names = names
            if vectors:
                self._dim = vectors[0].size
                self._matrix = np.vstack(vectors).astype(np.float32)
            else:
                self._matrix = np.zeros((0, self._dim), dtype=np.float32)
        log.info("gallery loaded: %d members, %d embeddings", len(names), len(member_ids))

    def add(self, member_id: str, name: str, vectors: list[np.ndarray]) -> None:
        prepared = []
        for vec in vectors:
            vec = np.asarray(vec, dtype=np.float32).reshape(-1)
            if vec.size != self._dim:
                raise ValueError(f"Embedding dimension mismatch: expected {self._dim}, got {vec.size}.")
            if not np.all(np.isfinite(vec)):
                raise ValueError("Embedding contains non-finite values.")
            norm = float(np.linalg.norm(vec))
            if norm > 1e-9:
                prepared.append(vec / norm)
        if not prepared:
            return
        with self._lock:
            self._matrix = np.vstack([self._matrix, np.vstack(prepared)]).astype(np.float32)
            self._member_ids.extend([member_id] * len(prepared))
            self._names[member_id] = name

    def remove_member(self, member_id: str) -> None:
        with self._lock:
            keep = [i for i, mid in enumerate(self._member_ids) if mid != member_id]
            self._matrix = self._matrix[keep] if keep else np.zeros((0, self._dim), dtype=np.float32)
            self._member_ids = [self._member_ids[i] for i in keep]
            self._names.pop(member_id, None)

    # -- queries -----------------------------------------------------------
    @property
    def member_count(self) -> int:
        with self._lock:
            return len(self._names)

    @property
    def embedding_count(self) -> int:
        with self._lock:
            return int(self._matrix.shape[0])

    def match(self, vector: np.ndarray, threshold: float, margin: float) -> MatchResult:
        """1:N identification with an ambiguity margin.

        A candidate must clear the absolute similarity threshold *and* beat the
        runner-up by ``margin``. If two enrolled people score almost equally we
        report ambiguity instead of guessing.
        """
        query = np.asarray(vector, dtype=np.float32).reshape(-1)
        if query.size != self._dim:
            return MatchResult(accepted=False, reason="dimension_mismatch")
        if not np.all(np.isfinite(query)):
            return MatchResult(accepted=False, reason="invalid_embedding")
        norm = float(np.linalg.norm(query))
        if norm <= 1e-9:
            return MatchResult(accepted=False, reason="invalid_embedding")
        query = query / norm

        with self._lock:
            if self._matrix.shape[0] == 0:
                return MatchResult(accepted=False, reason="no_candidates")
            scores = self._matrix @ query
            member_ids = list(self._member_ids)
            names = dict(self._names)

        # Best score per member (handles multiple enrolment photos).
        best: dict[str, float] = {}
        for idx, score in enumerate(scores):
            mid = member_ids[idx]
            value = float(score)
            if value > best.get(mid, -2.0):
                best[mid] = value
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        top_id, top_score = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else -1.0
        gap = top_score - second if len(ranked) > 1 else 1.0

        if top_score < threshold:
            return MatchResult(False, top_id, names.get(top_id), top_score, second, gap, "below_threshold")
        if len(ranked) > 1 and gap < margin:
            return MatchResult(False, top_id, names.get(top_id), top_score, second, gap, "ambiguous")
        return MatchResult(True, top_id, names.get(top_id), top_score, second, gap, "accepted")

    def best_similarity_for_member(self, vector: np.ndarray, member_id: str) -> float:
        query = np.asarray(vector, dtype=np.float32).reshape(-1)
        if query.size != self._dim or not np.all(np.isfinite(query)):
            return 0.0
        norm = float(np.linalg.norm(query))
        if norm <= 1e-9:
            return 0.0
        query = query / norm
        with self._lock:
            idxs = [i for i, mid in enumerate(self._member_ids) if mid == member_id]
            if not idxs:
                return 0.0
            return float(np.max(self._matrix[idxs] @ query))


GALLERY = FaceGallery()
