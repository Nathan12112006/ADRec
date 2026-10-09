from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import WorkflowError
from app.ctr.features import FEATURE_VERSION
from app.ctr.serving import CTRModel
from app.ctr.training import MODEL_VERSION
from app.models.records import Experiment
from app.schemas.experiments import ExperimentCreate

EXPERIMENT_ROUTING_LOCK = 912304771


def lock_experiment_routing(session: Session, *, exclusive: bool) -> None:
    function = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
    session.execute(text(f"SELECT {function}(:lock_key)"), {"lock_key": EXPERIMENT_ROUTING_LOCK})


def create_experiment(session: Session, body: ExperimentCreate, model: CTRModel) -> Experiment:
    model_id = model.model_id
    if model_id is None:
        raise WorkflowError(409, "model_unavailable", "A validated CTR model is required")
    record = Experiment(
        name=body.name.strip(),
        control_basis_points=body.control_basis_points,
        control_strategy=body.control_strategy,
        treatment_strategy=body.treatment_strategy,
        model_id=model_id,
        model_version=MODEL_VERSION,
        feature_version=FEATURE_VERSION,
        retrieval_mode=body.retrieval_mode,
        candidate_limit=body.candidate_limit,
        search_limit=body.search_limit,
        hnsw_ef_search=body.hnsw_ef_search,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_experiments(session: Session) -> list[Experiment]:
    return list(
        session.scalars(select(Experiment).order_by(Experiment.created_at.desc(), Experiment.id))
    )


def transition_experiment(
    session: Session, experiment_id: UUID, action: str, model: CTRModel
) -> Experiment:
    lock_experiment_routing(session, exclusive=True)
    record = session.scalar(
        select(Experiment).where(Experiment.id == experiment_id).with_for_update()
    )
    if record is None:
        raise WorkflowError(404, "experiment_not_found", "Experiment was not found")
    if action == "start":
        if record.status != "draft":
            raise WorkflowError(409, "invalid_experiment_transition", "Only a draft can start")
        if record.control_basis_points in (0, 10000):
            raise WorkflowError(
                422, "invalid_experiment_allocation", "Both variants require traffic"
            )
        if record.model_id != model.model_id or model.model_id is None:
            raise WorkflowError(
                409, "model_unavailable", "The experiment's pinned CTR model is unavailable"
            )
        try:
            session.execute(
                text(
                    "UPDATE experiments SET status='running', "
                    "started_at=clock_timestamp() WHERE id=:id"
                ),
                {"id": experiment_id},
            )
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise WorkflowError(
                409, "experiment_already_running", "Another ranking experiment is running"
            ) from error
    elif action == "stop":
        if record.status != "running":
            raise WorkflowError(
                409, "invalid_experiment_transition", "Only a running experiment can stop"
            )
        session.execute(
            text(
                "UPDATE experiments SET status='stopped', stopped_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": experiment_id},
        )
        session.commit()
    else:
        raise ValueError("unsupported action")
    session.refresh(record)
    return record
