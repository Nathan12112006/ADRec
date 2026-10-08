"""Shared bounds for candidate counts and filtered-search expansion."""

from typing import Annotated

from pydantic import Field

DEFAULT_CANDIDATE_LIMIT = 500
MAX_CANDIDATE_LIMIT = 500
MAX_SEARCH_LIMIT = 1_000_000
CandidateLimit = Annotated[int, Field(strict=True, ge=1, le=MAX_CANDIDATE_LIMIT)]
