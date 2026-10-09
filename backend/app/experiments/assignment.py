"""Versioned canonical assignment, independent of process hash and request order."""

import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

_USER_ID: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)])


class AssignmentConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    id: UUID
    salt: str = Field(pattern=r"^[0-9a-f]{64}$")
    assignment_version: Literal["sha256-bucket-v1"] = "sha256-bucket-v1"
    control_basis_points: int = Field(default=5000, strict=True, ge=0, le=10000)


def assign_variant(user_id: int, experiment: AssignmentConfig) -> Literal["control", "treatment"]:
    identity = _USER_ID.validate_python(user_id)
    payload = json.dumps(
        [experiment.assignment_version, str(experiment.id), experiment.salt, str(identity)],
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    bucket = int.from_bytes(digest, "big") * 10000 // (1 << 256)
    return "control" if bucket < experiment.control_basis_points else "treatment"
