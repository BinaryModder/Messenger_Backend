from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.deps import get_db
from services.chat_services import ChatService
from services.message_services import MessageService
from schemas.chat_schemas import ChatCreate, ChatUpdate, ChatResponse
from schemas.message_schemas import MessageCreate, MessageUpdate, MessageResponse

router = APIRouter(prefix="/api/v1/chats", tags=["chats"])


# ============ CHAT ENDPOINTS ============

@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_chat(chat_data: ChatCreate, db: Session = Depends(get_db)):
    try:
        chat = ChatService.create_chat(db, chat_data)
        return chat
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=list[ChatResponse])
def list_chats(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    chats = ChatService.get_all_chats(db, skip, limit)
    return chats


@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat(chat_id: int, db: Session = Depends(get_db)):
    chat = ChatService.get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


@router.patch("/{chat_id}", response_model=ChatResponse)
def update_chat(chat_id: int, chat_data: ChatUpdate, db: Session = Depends(get_db)):
    try:
        chat = ChatService.update_chat(db, chat_id, chat_data)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        return chat
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    try:
        deleted = ChatService.delete_chat(db, chat_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ============ MESSAGE ENDPOINTS ============

@router.post("/{chat_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def create_message(chat_id: int, message_data: MessageCreate, db: Session = Depends(get_db)):
    # Проверяем существование чата
    chat = ChatService.get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    
    # Убеждаемся что chat_id в пути совпадает с телом запроса
    if message_data.chat_id != chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="chat_id in path does not match chat_id in request body")
    
    try:
        message = MessageService.create_message(db, message_data)
        return message
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{chat_id}/messages", response_model=list[MessageResponse])
def get_messages(chat_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Проверяем существование чата
    chat = ChatService.get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    
    messages = MessageService.get_messages_by_chat(db, chat_id, skip, limit)
    return messages


@router.get("/{chat_id}/messages/{message_id}", response_model=MessageResponse)
def get_message(chat_id: int, message_id: int, db: Session = Depends(get_db)):
    # Проверяем существование чата
    chat = ChatService.get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    
    message = MessageService.get_message_by_id(db, message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    # Проверяем что сообщение принадлежит этому чату
    if message.chat_id != chat_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found in this chat")
    
    return message


@router.patch("/{chat_id}/messages/{message_id}", response_model=MessageResponse)
def update_message(chat_id: int, message_id: int, message_data: MessageUpdate, db: Session = Depends(get_db)):
    # Проверяем существование чата
    chat = ChatService.get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    
    # Проверяем существование сообщения и что оно в этом чате
    existing_message = MessageService.get_message_by_id(db, message_id)
    if not existing_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    if existing_message.chat_id != chat_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found in this chat")
    
    try:
        message = MessageService.update_message(db, message_id, message_data)
        return message
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{chat_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(chat_id: int, message_id: int, db: Session = Depends(get_db)):
    # Проверяем существование чата
    chat = ChatService.get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    
    # Проверяем существование сообщения и что оно в этом чате
    existing_message = MessageService.get_message_by_id(db, message_id)
    if not existing_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    if existing_message.chat_id != chat_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found in this chat")
    
    try:
        deleted = MessageService.delete_message(db, message_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
