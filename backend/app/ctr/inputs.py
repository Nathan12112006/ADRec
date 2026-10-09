"""Validated, ordered raw input for the persisted preprocessing/model pipeline."""

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

FEATURE_COLUMNS = (
    "shared_interest_count",
    "category_match",
    "ad_category",
    "device_type",
    "age_group",
)


class FeatureInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    shared_interest_count: int = Field(ge=0)
    category_match: bool
    ad_category: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
    age_group: str = Field(min_length=1)

    def ordered(self) -> list[int | bool | str]:
        return [getattr(self, name) for name in FEATURE_COLUMNS]


def feature_matrix(features: Iterable[Mapping[str, Any]]) -> NDArray[np.object_]:
    """Only shared builder output is accepted; metadata and labels are rejected."""
    rows = [FeatureInput.model_validate(row).ordered() for row in features]
    return np.asarray(rows, dtype=object).reshape((-1, len(FEATURE_COLUMNS)))
