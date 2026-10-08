"""Pure baseline selection; persistence and HTTP workflows belong to callers."""

from app.ranking.baseline import BaselineCandidate, select_baseline

__all__ = ["BaselineCandidate", "select_baseline"]
