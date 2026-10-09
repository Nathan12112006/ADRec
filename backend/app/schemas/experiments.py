from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

StrategyName = Literal["interest-overlap", "expected-value"]


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    control_basis_points: int = Field(default=5000, strict=True, ge=0, le=10000)
    control_strategy: StrategyName = "interest-overlap"
    treatment_strategy: StrategyName = "expected-value"
    retrieval_mode: Literal["exact", "hnsw"] = "exact"
    candidate_limit: int = Field(default=500, strict=True, ge=1, le=500)
    search_limit: int = Field(default=4000, strict=True, ge=1, le=1000000)
    hnsw_ef_search: int | None = Field(default=None, strict=True, ge=1, le=1000000)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @model_validator(mode="after")
    def validate_retrieval(self) -> "ExperimentCreate":
        if self.search_limit < self.candidate_limit:
            raise ValueError("search_limit must be at least candidate_limit")
        if (self.retrieval_mode == "exact") != (self.hnsw_ef_search is None):
            raise ValueError("hnsw_ef_search is required only for hnsw retrieval")
        return self


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: Literal["draft", "running", "stopped"]
    control_basis_points: int
    control_strategy: str
    treatment_strategy: str
    model_id: str
    retrieval_mode: str
    candidate_limit: int
    search_limit: int
    hnsw_ef_search: int | None
    created_at: datetime
    started_at: datetime | None
    stopped_at: datetime | None


class ExperimentResultsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    experiment_status: Literal["draft", "running", "stopped"]
    synthetic: bool
    statistical_test: None
    cohort_start: datetime
    cohort_end_exclusive: datetime
    as_of: datetime
    provisional: bool
    event_window_hours: int
    event_windows_closed_through: datetime
    variants: dict[str, dict[str, object]]
    comparison: dict[str, dict[str, object]]
    latency_populations: list[dict[str, object]]
    telemetry: dict[str, object]
