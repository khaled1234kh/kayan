"""Typed ORM models.

Design rules:
- Domain facts live in columns; structured extras go in a JSON field, never in a
  free-text log.
- External participants (e.g. ``ext:supplier``) are represented by an
  ``external_sender`` value rather than fake employee rows.
- Events carry a monotonic ``sequence`` in addition to their timestamp, because
  the client depends on a deterministic order and wall clocks are not ordering.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.session import Base

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite in tests).
JSONVariant = JSONB().with_variant(JSON(), "sqlite")


def enum_column(enum_cls: type[enum.Enum], length: int = 32) -> SAEnum:
    """String-backed enum column.

    Stores plain VARCHAR (portable — no PostgreSQL ``ENUM`` type to migrate) while
    still giving Python-side typing: values come back as enum members, so a typo
    in a status or mode is a type error rather than a silent string.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentKind(str, enum.Enum):
    HUMAN = "human"
    AI = "ai"


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    AWAITING_APPROVAL = "awaiting_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class MessageType(str, enum.Enum):
    TASK = "task"
    QUESTION = "question"
    RESPONSE = "response"
    HANDOFF = "handoff"
    INSTRUCTION = "instruction"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"


class HandoffStatus(str, enum.Enum):
    SENT = "sent"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    REJECTED = "rejected"


class Condition(str, enum.Enum):
    """The two experimental conditions. Also used to label a plain run."""

    BASELINE = "baseline"
    ENFORCED = "enforced"


class Agent(Base):
    """A worker seat. Mirrors the canonical frontend agent profile."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[AgentKind] = mapped_column(enum_column(AgentKind, 16), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text)
    #: JSON array of descriptive capability strings.
    capabilities: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    restrictions: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="assigned_agent")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Agent {self.id} {self.kind}>"


class Task(Base):
    """A unit of work. ``parent_task_id`` models delegation (Manager → Sales)."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        enum_column(TaskStatus), default=TaskStatus.OPEN, nullable=False
    )
    assigned_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), index=True
    )
    parent_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )

    assigned_agent: Mapped[Agent | None] = relationship(back_populates="tasks")
    #: Delegation edge: the task this one was carved out of.
    parent_task: Mapped["Task | None"] = relationship(
        back_populates="subtasks", remote_side=[id]
    )
    subtasks: Mapped[list["Task"]] = relationship(back_populates="parent_task")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Task {self.id} {self.status}>"


class Message(Base):
    """Agent-to-agent communication, including external senders."""

    __tablename__ = "messages"
    __table_args__ = (
        # Exactly one sender: a seated agent or an external sender id.
        CheckConstraint(
            "(from_agent_id IS NOT NULL) <> (external_sender IS NOT NULL)",
            name="ck_message_single_sender",
        ),
        Index("ix_messages_to_created", "to_agent_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), index=True
    )
    external_sender: Mapped[str | None] = mapped_column(String(64))
    to_agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[MessageType] = mapped_column(enum_column(MessageType), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    #: Structured payload the recipient acts on (e.g. available/required counts).
    context: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    expected_output: Mapped[str | None] = mapped_column(Text)
    #: Threading: the message this one answers.
    reply_to_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    from_agent: Mapped[Agent | None] = relationship(foreign_keys=[from_agent_id])
    to_agent: Mapped[Agent] = relationship(foreign_keys=[to_agent_id])
    reply_to: Mapped["Message | None"] = relationship(
        back_populates="replies", remote_side=[id]
    )
    replies: Mapped[list["Message"]] = relationship(back_populates="reply_to")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Message {self.id} {self.type}>"


class Handoff(Base):
    """Explicit transfer of an objective between agents."""

    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    to_agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    #: JSON array of hard limits the receiving agent must respect.
    constraints: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[HandoffStatus] = mapped_column(
        enum_column(HandoffStatus, 16), default=HandoffStatus.SENT, nullable=False
    )
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )

    from_agent: Mapped[Agent] = relationship(foreign_keys=[from_agent_id])
    to_agent: Mapped[Agent] = relationship(foreign_keys=[to_agent_id])
    source_message: Mapped[Message | None] = relationship(foreign_keys=[source_message_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Handoff {self.id} {self.status}>"


class Event(Base):
    """Immutable record of something that already happened.

    ``sequence`` provides deterministic ordering within a stream; ``timestamp``
    is for humans and cross-run correlation. Clients replay by ``sequence``.
    """

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("stream_id", "sequence", name="uq_event_stream_sequence"),
        Index("ix_events_occurred", "timestamp"),
        Index("ix_events_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Monotonic per stream. Allocation happens inside the same transaction as the
    #: insert, so ordering never depends on wall-clock resolution.
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: Stream/run grouping (e.g. an experiment run id, or a live session id).
    stream_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    actor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    target_id: Mapped[str | None] = mapped_column(String(64))
    task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    #: The workflow run this event belongs to. Events are owned by exactly one
    #: execution, which is what makes a run's history auditable in isolation.
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    #: Deterministic logical offset within the owning run, in milliseconds.
    #:
    #: Present on workflow events only. ``timestamp`` is always real UTC; this
    #: carries the reproducible workflow position used for experiment timings so
    #: the two are never conflated.
    clock_offset_ms: Mapped[int | None] = mapped_column(Integer)
    #: Structured payload (message object, policy decision, intent, ...).
    payload: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Event {self.sequence} {self.event_type}>"


class ExperimentStatus(str, enum.Enum):
    """Lifecycle of one baseline-vs-enforced comparison."""

    RUNNING = "running"
    COMPLETED = "completed"
    #: Some trials finished, some failed. Reported honestly, never as success.
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"


class Experiment(Base):
    """One baseline-versus-enforced comparison.

    Holds identity, configuration and lifecycle. It stores no metrics: every
    number is derived from the individual trial records, which are
    ``WorkflowRun`` rows.
    """

    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: The command that started it, for idempotency.
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Reproducibility key shared by both conditions, e.g. KAYAN-DEMO-1042.
    seed: Mapped[str] = mapped_column(String(64), nullable=False)
    runs_per_condition: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ExperimentStatus] = mapped_column(
        enum_column(ExperimentStatus, 24), default=ExperimentStatus.RUNNING, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Experiment {self.id} {self.status}>"


class WorkflowRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowRun(Base):
    """One execution of the KAYAN workflow.

    This is the single run record for the whole system: a commanded order from
    ``request_order``, or an experimental trial from ``run_comparison``. When it
    belongs to an experiment it also carries its condition, seed and run index;
    those stay null for an ordinary order run.

    Every count here is derived from the run's own events — never authored.
    """

    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_order_status", "order_id", "status"),
        Index("ix_workflow_runs_experiment", "experiment_id", "condition", "run_index"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: The command that started it, for correlation with the client.
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[WorkflowRunStatus] = mapped_column(
        enum_column(WorkflowRunStatus, 16), default=WorkflowRunStatus.RUNNING, nullable=False
    )
    #: Monotonic, to make a slow or repeated order visibly distinct.
    run_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # -- experimental trial identity (null for an ordinary order run) -------
    experiment_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), index=True
    )
    condition: Mapped[Condition | None] = mapped_column(enum_column(Condition, 16))
    #: The reproducibility key for this trial; identical across a condition pair.
    seed: Mapped[str | None] = mapped_column(String(64))

    # -- derived metrics ---------------------------------------------------
    #: Logical workflow duration: last event minus first, from event timestamps.
    duration_ms: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    #: Real elapsed machine time to execute the run. Kept separate from the
    #: logical duration so the two are never conflated.
    wall_clock_ms: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    handoff_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    policy_decision_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    denial_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    violation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovery_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unauthorized_action_attempted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    unauthorized_action_allowed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    #: JSON array of measured intervals, named and in milliseconds.
    timings: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    final_state: Mapped[str | None] = mapped_column(String(64))
    #: Populated only when the run failed; never fabricated as success.
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<WorkflowRun {self.id} {self.status}>"


class CommandRequest(Base):
    """Idempotency record for an inbound command.

    ``request_id`` is the primary key, so a command delivered twice can be
    detected by the database rather than by fragile in-memory bookkeeping.
    """

    __tablename__ = "command_requests"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    command: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(64))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Why it was rejected, when it was.
    reason: Mapped[str | None] = mapped_column(String(128))
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<CommandRequest {self.request_id} accepted={self.accepted}>"