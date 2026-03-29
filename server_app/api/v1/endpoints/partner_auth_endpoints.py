"""Авторизация партнёра: регистрация, логин, профиль."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_partner
from core.security import hash_password, verify_password, create_access_token
from models.business_rep_model import BusinessRepresentative

router = APIRouter(prefix="/partner/auth", tags=["partner-auth"])


# --------------------------------------------------------------------------- #
# Схемы                                                                        #
# --------------------------------------------------------------------------- #

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    login: str = Field(..., description="username или email")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    partner_id: int
    username: str
    full_name: Optional[str]


class PartnerProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    phone: Optional[str]
    country: Optional[str]
    bio: Optional[str]
    profile_image_url: Optional[str]
    is_active: bool
    average_rating: float
    total_places: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --------------------------------------------------------------------------- #
# Эндпоинты                                                                    #
# --------------------------------------------------------------------------- #

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Регистрация нового партнёра."""
    existing = db.execute(
        select(BusinessRepresentative).where(
            (BusinessRepresentative.username == payload.username)
            | (BusinessRepresentative.email == payload.email)
        )
    ).scalars().first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Партнёр с таким username или email уже существует",
        )

    partner = BusinessRepresentative(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)

    token = create_access_token(subject=partner.id)
    return TokenResponse(
        access_token=token,
        partner_id=partner.id,
        username=partner.username,
        full_name=partner.full_name,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Вход по username или email + пароль."""
    login_val = payload.login.strip()
    partner = db.execute(
        select(BusinessRepresentative).where(
            (BusinessRepresentative.username == login_val)
            | (BusinessRepresentative.email == login_val)
        )
    ).scalars().first()

    if partner is None or not verify_password(payload.password, partner.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    if not partner.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт деактивирован",
        )

    token = create_access_token(subject=partner.id)
    return TokenResponse(
        access_token=token,
        partner_id=partner.id,
        username=partner.username,
        full_name=partner.full_name,
    )


@router.get("/me", response_model=PartnerProfileResponse)
def get_me(
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> PartnerProfileResponse:
    """Возвращает профиль текущего авторизованного партнёра."""
    return PartnerProfileResponse.model_validate(current_partner)
