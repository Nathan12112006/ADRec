from uuid import UUID

import pytest

from app.experiments.assignment import AssignmentConfig, assign_variant


def test_known_assignment_uses_stored_identity_and_default_half_allocation() -> None:
    config = AssignmentConfig(id=UUID(int=1), salt="0" * 64)
    assert config.assignment_version == "sha256-bucket-v1"
    assert config.control_basis_points == 5000
    assert assign_variant(2, config) == "control"


@pytest.mark.parametrize(
    "allocation,expected",
    [(0, "treatment"), (8307, "treatment"), (8308, "control"), (10000, "control")],
)
def test_known_digest_bucket_obeys_exact_allocation_boundary(
    allocation: int, expected: str
) -> None:
    # Published vector for user1: digest d4ad52b98974bbae... => bucket8307.
    config = AssignmentConfig(id=UUID(int=1), salt="0" * 64, control_basis_points=allocation)
    assert assign_variant(1, config) == expected


def test_known_assignments_reproduce_in_fresh_processes_with_different_hash_seeds() -> None:
    import json
    import os
    import subprocess
    import sys

    script = """
import json
from uuid import UUID
from app.experiments.assignment import AssignmentConfig, assign_variant
config=AssignmentConfig(id=UUID(int=1),salt='0'*64)
print(json.dumps([assign_variant(user,config) for user in [1,2,3,42,9223372036854775807]]))
"""
    for seed in ("0", "123"):
        output = subprocess.check_output(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONHASHSEED": seed},
            text=True,
            timeout=20,
        )
        assert json.loads(output) == ["treatment", "control", "treatment", "control", "control"]


@pytest.mark.parametrize("user_id", [0, -1, 2**63, True, "1"])
def test_invalid_synthetic_user_identity_is_rejected(user_id: object) -> None:
    from typing import Any, cast

    with pytest.raises(ValueError):
        assign_variant(cast(Any, user_id), AssignmentConfig(id=UUID(int=1), salt="0" * 64))


@pytest.mark.parametrize(
    "change",
    [
        {"assignment_version": "python-hash"},
        {"salt": "bad"},
        {"salt": "f" * 65},
        {"control_basis_points": -1},
        {"control_basis_points": 10001},
        {"control_basis_points": True},
    ],
)
def test_invalid_assignment_contract_is_rejected(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        AssignmentConfig.model_validate({"id": UUID(int=1), "salt": "0" * 64, **change})


def test_a_new_experiment_identity_can_reassign_the_same_user() -> None:
    original = AssignmentConfig(id=UUID(int=1), salt="0" * 64)
    new_experiment = AssignmentConfig(id=UUID(int=4), salt="0" * 64)
    assert assign_variant(1, original) == "treatment"
    assert assign_variant(1, new_experiment) == "control"
