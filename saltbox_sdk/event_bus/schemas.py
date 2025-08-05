from pydantic import BaseModel


class EventBusBaseMessage(BaseModel):
    target: str | None = None
