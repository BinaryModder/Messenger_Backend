from fastapi import APIRouter, Depends
from api.deps import get_db

from schemas.user_chat_schemas import UserChatCreate, UserChatResponse


router = APIRouter(prefix="/api/v1/chats", tags=["chats"])
