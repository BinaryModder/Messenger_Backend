from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class MessageBase(BaseModel):
    message_text: str


class MessageCreate(MessageBase):
    chat_id: int
    sender_id: int


class MessageUpdate(BaseModel):
    message_text: Optional[str] = None


class MessageResponse(MessageBase):
    message_id: int
    chat_id: int
    sender_id: int
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)
