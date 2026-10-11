"""Message API contract."""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import ApiSchema


class MessageOut(ApiSchema):
    """Typed agent communication.

    Exactly one of ``from_agent_id`` / ``external_sender`` is populated, so an
    external sender such as ``ext:supplier`` stays possible without creating a
    fake employee record.
    """

    id: str
    from_agent_id: str | None = None
    external_sender: str | None = None
    to_agent_id: str
    type: str
    subject: str
    instructions: str | None = None
    context: dict = {}
    expected_output: str | None = None
    #: Threading preserved.
    reply_to_message_id: str | None = None
    task_id: str | None = None
    delivered: bool = False
    created_at: datetime