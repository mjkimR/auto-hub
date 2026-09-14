from typing import Any

from pydantic import BaseModel


class TaskSpecResponse(BaseModel):
    name: str
    description: str
    payload_schema: dict[str, Any] | None = None
