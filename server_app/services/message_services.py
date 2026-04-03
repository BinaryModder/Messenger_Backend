from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.message_model import Message
from schemas.message_schemas import MessageCreate, MessageUpdate
from typing import Optional


class MessageService:
    @staticmethod
    def create_message(db: Session, message_data: MessageCreate) -> Message:
        message = Message(
            chat_id=message_data.chat_id,
            sender_id=message_data.sender_id,
            message_text=message_data.message_text
        )

        db.add(message)
        try:
            db.commit()
            db.refresh(message)
            return message
        except IntegrityError:
            db.rollback()
            raise ValueError("Error creating message - invalid chat_id or sender_id")

    @staticmethod
    def get_message_by_id(db: Session, message_id: int) -> Optional[Message]:
        return db.query(Message).filter(Message.message_id == message_id).first()

    @staticmethod
    def get_messages_by_chat(db: Session, chat_id: int, skip: int = 0, limit: int = 100) -> list[Message]:
        return (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.sent_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_message(db: Session, message_id: int, message_data: MessageUpdate) -> Optional[Message]:
        message = db.query(Message).filter(Message.message_id == message_id).first()
        if not message:
            return None

        if message_data.message_text is not None:
            message.message_text = message_data.message_text

        try:
            db.commit()
            db.refresh(message)
            return message
        except IntegrityError:
            db.rollback()
            raise ValueError("Error updating message")

    @staticmethod
    def delete_message(db: Session, message_id: int) -> bool:
        message = db.query(Message).filter(Message.message_id == message_id).first()
        if not message:
            return False

        db.delete(message)
        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            raise ValueError("Error deleting message")

    @staticmethod
    def get_all_messages(db: Session, skip: int = 0, limit: int = 100) -> list[Message]:
        return db.query(Message).order_by(Message.sent_at.desc()).offset(skip).limit(limit).all()
