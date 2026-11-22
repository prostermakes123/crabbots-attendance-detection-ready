"""Multi-face tracking with temporal evidence aggregation.

Design notes
------------
* Association is greedy IoU matching. At 8 FPS a walking person overlaps their
  previous box heavily, and ``max_age`` lets a track survive detector misses.
* Each track keeps a bounded window of per-frame recognition evidence. The
  decision is made on the *whole window*, so one lucky blurry frame cannot
  outvote several clear ones, and a single unlucky frame cannot erase a person.
* Tracks are independent, so several people in frame cannot contaminate each
  other's identity votes.
* Nothing here is random: the same frame sequence always yields the same tracks,
  which keeps tests deterministic.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Iterable

from .detector import Detection
from .gallery import MatchResult


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    ix0, iy0 = max(ax, bx), max(ay, by)
    ix1, iy1 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return float(inter / union) if union > 0 else 0.0


@dataclass
class Evidence:
    member_id: str | None
    name: str | None
    similarity: float
    accepted: bool
    frame: int


@dataclass
class Track:
    id: int
    bbox: tuple[float, float, float, float]
    created_frame: int
    last_frame: int
    hits: int = 1
    missed: int = 0
    status: str = "pending"  # pending | recognized | unknown
    member_id: str | None = None
    member_name: str | None = None
    confidence: float = 0.0
    best_similarity: float = 0.0
    attendance_recorded: bool = False
    unknown_logged: bool = False
    session_id: str | None = None
    evidence: deque[Evidence] = field(default_factory=deque)

    def add_evidence(self, item: Evidence, window: int) -> None:
        if self.evidence.maxlen != window:
            self.evidence = deque(self.evidence, maxlen=window)
        self.evidence.append(item)

    def reset_identity(self) -> None:
        self.evidence.clear()
        self.status = "pending"
        self.member_id = None
        self.member_name = None
        self.confidence = 0.0
        self.attendance_recorded = False
        self.unknown_logged = False


class MultiFaceTracker:
    def __init__(self) -> None:
        self._next_id = 1
        self.tracks: dict[int, Track] = {}
        self.frame_index = 0

    def reset(self) -> None:
        self.tracks.clear()
        self.frame_index = 0
        self._next_id = 1

    # -- association -------------------------------------------------------
    def _associate(
        self, detections: list[Detection], iou_threshold: float
    ) -> tuple[dict[int, int], list[int]]:
        """Return {track_id: detection_index} and unmatched detection indices."""
        pairs: list[tuple[float, int, int]] = []
        for tid, track in self.tracks.items():
            for di, det in enumerate(detections):
                score = iou(track.bbox, det.bbox)
                if score >= iou_threshold:
                    pairs.append((score, tid, di))
        pairs.sort(reverse=True)
        used_tracks: set[int] = set()
        used_dets: set[int] = set()
        matches: dict[int, int] = {}
        for _, tid, di in pairs:
            if tid in used_tracks or di in used_dets:
                continue
            matches[tid] = di
            used_tracks.add(tid)
            used_dets.add(di)
        unmatched = [di for di in range(len(detections)) if di not in used_dets]
        return matches, unmatched

    # -- main update -------------------------------------------------------
    def update(
        self,
        detections: list[Detection],
        embeddings: list,
        matches: list[MatchResult],
        settings: dict[str, Any],
    ) -> list[Track]:
        self.frame_index += 1
        frame = self.frame_index
        iou_threshold = float(settings.get("track_iou_threshold", 0.30))
        max_age = int(settings.get("track_max_age_frames", 24))
        min_hits = int(settings.get("track_min_hits", 3))
        window = int(settings.get("evidence_window", 12))
        consistency = float(settings.get("evidence_consistency", 0.60))
        threshold = float(settings.get("recognition_threshold", 0.42))

        associations, unmatched = self._associate(detections, iou_threshold)

        # Age existing tracks that were not matched.
        for tid, track in list(self.tracks.items()):
            if tid not in associations:
                track.missed += 1
                if track.missed > max_age:
                    self.tracks.pop(tid, None)

        # Update matched tracks.
        for tid, di in associations.items():
            track = self.tracks[tid]
            det = detections[di]
            track.bbox = det.bbox
            track.last_frame = frame
            track.hits += 1
            track.missed = 0
            result = matches[di]
            self._apply_evidence(track, result, frame, window)
            self._decide(track, frame, min_hits, consistency, threshold, window)

        # Create tracks for unmatched detections.
        for di in unmatched:
            det = detections[di]
            track = Track(id=self._next_id, bbox=det.bbox, created_frame=frame, last_frame=frame)
            self._next_id += 1
            self.tracks[track.id] = track
            self._apply_evidence(track, matches[di], frame, window)
            self._decide(track, frame, min_hits, consistency, threshold, window)

        return list(self.tracks.values())

    @staticmethod
    def _apply_evidence(track: Track, result: MatchResult, frame: int, window: int) -> None:
        track.best_similarity = max(track.best_similarity, result.similarity)
        track.add_evidence(
            Evidence(
                member_id=result.member_id if result.accepted else None,
                name=result.name if result.accepted else None,
                similarity=result.similarity,
                accepted=result.accepted,
                frame=frame,
            ),
            window,
        )

    @staticmethod
    def _decide(
        track: Track,
        frame: int,
        min_hits: int,
        consistency: float,
        threshold: float,
        window: int,
    ) -> None:
        votes = [e for e in track.evidence if e.accepted and e.member_id]
        total = len(track.evidence)
        if track.hits < min_hits or total < min_hits:
            track.status = "pending"
            return

        if votes:
            counts = Counter(e.member_id for e in votes)
            winner_id, winner_count = counts.most_common(1)[0]
            support = winner_count / max(1, total)
            winner_votes = [e for e in votes if e.member_id == winner_id]
            mean_sim = sum(e.similarity for e in winner_votes) / len(winner_votes)
            recent = any(e.frame >= frame - 2 for e in winner_votes)
            if (
                winner_count >= min_hits
                and support >= consistency
                and mean_sim >= threshold
                and recent
            ):
                if track.member_id != winner_id:
                    track.attendance_recorded = False
                    track.unknown_logged = False
                track.status = "recognized"
                track.member_id = winner_id
                track.member_name = winner_votes[0].name
                track.confidence = mean_sim
                return

        # No coherent identity: report unknown rather than guessing.
        track.status = "unknown"
        track.member_id = None
        track.member_name = None
        track.confidence = track.best_similarity
        track.attendance_recorded = False

    # -- views -------------------------------------------------------------
    def view(self, track: Track, settings: dict[str, Any]) -> dict[str, Any]:
        return {
            "track_id": track.id,
            "bbox": [round(v, 1) for v in track.bbox],
            "status": track.status,
            "member_id": track.member_id,
            "name": track.member_name,
            "confidence": round(float(track.confidence), 4),
            "best_similarity": round(float(track.best_similarity), 4),
            "hits": track.hits,
            "missed": track.missed,
            "evidence": len(track.evidence),
            "attendance_recorded": track.attendance_recorded,
        }

    def active_count(self, max_age: int = 24) -> int:
        return sum(1 for t in self.tracks.values() if t.missed <= max_age)
