from pydantic import BaseModel

from saltbox_sdk.db.schemas_base import UserShort


class EventBusBaseMessage(BaseModel):
    sender: str
    target: str | None = None
    user: UserShort | None = None
