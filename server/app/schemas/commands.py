"""Client -> server command protocol.

The bridge gained exactly one write command. The distinction is explicit and
kept in the two directions:

    CLIENT -> SERVER   {kind: "command", ...}      validated against this module
    SERVER -> CLIENT   business events             the existing event contract

Protocol frames are never business events, and command metadata is never mixed
into an event payload. An unrecognised or malformed command is rejected here,
before it can reach the runtime.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

#: The only commands implemented. Anything else is refused by name.
SUPPORTED_COMMANDS = ("request_order", "run_comparison", "run_autonomous")

#: Deterministic demonstration order.
DEFAULT_ORDER_ID = "1042"

#: Reproducibility key for the experiment scenario.
DEFAULT_SEED = "KAYAN-DEMO-1042"

#: Default repeated trials per condition.
DEFAULT_RUNS_PER_CONDITION = 10

#: Guard rail for a research command.
MAX_RUNS_PER_CONDITION = 50


class RequestOrderCommand(BaseModel):
    """``request_order``: ask the backend to execute the order workflow.

    The backend owns the workflow; the client only chooses which order to run.
    """

    kind: Literal["command"] = "command"
    command: Literal["request_order"] = "request_order"
    request_id: str = Field(alias="requestId", min_length=1, max_length=64)
    order_id: str = Field(default=DEFAULT_ORDER_ID, alias="orderId", max_length=32)

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    def to_frame(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class RunComparisonCommand(BaseModel):
    """``run_comparison``: one coordinated baseline-vs-enforced comparison.

    Deliberately a single command: the two conditions are one experiment, not two
    independent runs that could drift apart.
    """

    kind: Literal["command"] = "command"
    command: Literal["run_comparison"] = "run_comparison"
    request_id: str = Field(alias="requestId", min_length=1, max_length=64)
    order_id: str = Field(default=DEFAULT_ORDER_ID, alias="orderId", max_length=32)
    seed: str = Field(default=DEFAULT_SEED, alias="seed", min_length=1, max_length=64)
    runs_per_condition: int = Field(
        default=DEFAULT_RUNS_PER_CONDITION,
        alias="runsPerCondition",
        ge=1,
        le=MAX_RUNS_PER_CONDITION,
    )

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    def to_frame(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class RunAutonomousCommand(BaseModel):
    """``run_autonomous``: work the active company's board until it is done.

    The loop staffs each actionable task through the Manager, executes it
    through budget and TrustGate, and streams the resulting task events over
    the already-open socket. It stops on target reached, budget exhausted, an
    empty board, or the safety bound. ``companyId`` is optional: omitted, the
    company holding the single active slot is used.
    """

    kind: Literal["command"] = "command"
    command: Literal["run_autonomous"] = "run_autonomous"
    request_id: str = Field(alias="requestId", min_length=1, max_length=64)
    company_id: str | None = Field(default=None, alias="companyId", max_length=64)
    max_iterations: int = Field(
        default=50,
        alias="maxIterations",
        ge=1,
        le=200,
    )

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    def to_frame(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


Command = RequestOrderCommand | RunComparisonCommand | RunAutonomousCommand


class ProtocolError(BaseModel):
    """Returned to the client when a frame cannot be accepted."""

    kind: Literal["command_error"] = "command_error"
    request_id: str | None = Field(default=None, alias="requestId")
    code: str
    message: str

    model_config = ConfigDict(populate_by_name=True)

    def to_frame(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class CommandAck(BaseModel):
    """Protocol acknowledgement.

    This is *not* the business result: it only says the command was understood
    and accepted (or refused). For a comparison, ``experimentId`` identifies the
    experiment to poll; it does not mean the experiment has finished.

    The business outcome is the persisted event stream, which the client already
    receives over the same socket.
    """

    kind: Literal["command_ack"] = "command_ack"
    request_id: str | None = Field(default=None, alias="requestId")
    command: str | None = None
    accepted: bool
    reason: str | None = None
    run_id: str | None = Field(default=None, alias="runId")
    experiment_id: str | None = Field(default=None, alias="experimentId")

    model_config = ConfigDict(populate_by_name=True)

    def to_frame(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


def parse_command(raw: str | bytes | dict[str, Any]) -> Command | ProtocolError:
    """Validate one inbound frame.

    Returns the typed command, or a ``ProtocolError`` describing exactly why it
    was refused. Never raises: a bad frame is a protocol outcome, not a crash.
    """
    if isinstance(raw, (str, bytes)):
        import json

        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return ProtocolError(
                code="malformed_frame",
                message="Frame is not valid JSON",
            )
    else:
        data = raw

    if not isinstance(data, dict):
        return ProtocolError(code="malformed_frame", message="Frame must be a JSON object")

    request_id = data.get("requestId") if isinstance(data.get("requestId"), str) else None

    kind = data.get("kind")
    if kind != "command":
        return ProtocolError(
            request_id=request_id,
            code="unsupported_frame_kind",
            message=f"Unsupported frame kind: {kind!r}. Only 'command' is accepted.",
        )

    name = data.get("command")
    if name not in SUPPORTED_COMMANDS:
        return ProtocolError(
            request_id=request_id,
            code="unknown_command",
            message=f"Unknown command: {name!r}. Supported: {', '.join(SUPPORTED_COMMANDS)}.",
        )

    model = (
        RequestOrderCommand
        if name == "request_order"
        else RunComparisonCommand
        if name == "run_comparison"
        else RunAutonomousCommand
    )
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        detail = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        return ProtocolError(
            request_id=request_id,
            code="invalid_command",
            message=detail or "Command failed validation",
        )
