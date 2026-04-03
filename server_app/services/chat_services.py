from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.chat_model import Chat
from schemas.chat_schemas import ChatCreate, ChatUpdate
from typing import Optional


class ChatService:
    @staticmethod
    def create_chat(db: Session, chat_data: ChatCreate) -> Chat:
        chat = Chat(
            chat_name=chat_data.chat_name,
            is_group_chat=chat_data.is_group_chat
        )

        db.add(chat)
        try:
            db.commit()
            db.refresh(chat)
            return chat
        except IntegrityError:
            db.rollback()
            raise ValueError("Error creating chat")

    @staticmethod
    def get_chat_by_id(db: Session, chat_id: int) -> Optional[Chat]:
        return db.query(Chat).filter(Chat.chat_id == chat_id).first()

    @staticmethod
    def update_chat(db: Session, chat_id: int, chat_data: ChatUpdate) -> Optional[Chat]:
        chat = db.query(Chat).filter(Chat.chat_id == chat_id).first()
        if not chat:
            return None

        if chat_data.chat_name is not None:
            chat.chat_name = chat_data.chat_name
        if chat_data.is_group_chat is not None:
            chat.is_group_chat = chat_data.is_group_chat

        try:
            db.commit()
            db.refresh(chat)
            return chat
        except IntegrityError:
            db.rollback()
            raise ValueError("Error updating chat")

    @staticmethod
    def delete_chat(db: Session, chat_id: int) -> bool:
        chat = db.query(Chat).filter(Chat.chat_id == chat_id).first()
        if not chat:
            return False

        db.delete(chat)
        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            raise ValueError("Error deleting chat")

    @staticmethod
    def get_all_chats(db: Session, skip: int = 0, limit: int = 100) -> list[Chat]:
        return db.query(Chat).offset(skip).limit(limit).all()
