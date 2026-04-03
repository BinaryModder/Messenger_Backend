from fastapi import APIRouter
from api.v1.endpoints import user_endpoints, chat_endpoints

api_router = APIRouter()

api_router.include_router(user_endpoints.router)
api_router.include_router(chat_endpoints.router)
