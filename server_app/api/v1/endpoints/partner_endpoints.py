"""Эндпоинты кабинета партнёра: места бизнеса и спецпредложения."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from api.deps import get_db, get_current_partner
from models import Place, PlaceImage, SpecialOffer
from models.business_rep_model import BusinessRepresentative
from schemas import SpecialOfferCreate, SpecialOfferUpdate, SpecialOfferWithPlace

router = APIRouter(prefix="/partner", tags=["partner"])


class PartnerPlaceItem(BaseModel):
    place_id: int
    name: str
    place_type: str | None
    location: str | None
    price: float | None
    photo: str
    interesting_fact: str | None
    cluster_id: str | None


@router.get("/places", response_model=List[PartnerPlaceItem])
def list_partner_places(
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> List[PartnerPlaceItem]:
    """Список мест текущего партнёра."""
    stmt = (
        select(Place)
        .where(Place.business_id == current_partner.id)
        .order_by(Place.place_id)
        .options(joinedload(Place.images), selectinload(Place.special_offers))
    )
    places = list(db.execute(stmt).unique().scalars().all())

    result: List[PartnerPlaceItem] = []
    for p in places:
        imgs = list(p.images) if p.images else []
        photo = imgs[0].image_url if imgs else ""
        result.append(
            PartnerPlaceItem(
                place_id=p.place_id,
                name=p.name or "",
                place_type=p.place_type,
                location=p.location,
                price=float(p.price) if p.price is not None else None,
                photo=photo,
                interesting_fact=p.interesting_fact,
                cluster_id=p.cluster_id,
            )
        )
    return result


@router.get("/special-offers", response_model=List[SpecialOfferWithPlace])
def list_partner_special_offers(
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> List[SpecialOfferWithPlace]:
    """Список спецпредложений текущего партнёра."""
    stmt = (
        select(SpecialOffer)
        .where(SpecialOffer.business_id == current_partner.id)
        .order_by(SpecialOffer.start_date.desc())
        .options(joinedload(SpecialOffer.place))
    )
    offers = list(db.execute(stmt).unique().scalars().all())

    return [
        SpecialOfferWithPlace(
            id=o.id,
            place_id=o.place_id,
            business_id=o.business_id,
            title=o.title,
            description=o.description,
            discount_percent=float(
                o.discount_percent) if o.discount_percent is not None else None,
            special_price=o.special_price,
            start_date=o.start_date,
            end_date=o.end_date,
            created_at=o.created_at,
            updated_at=o.updated_at,
            place_name=o.place.name if o.place else "",
            place_location=o.place.location if o.place else None,
            place_price=o.place.price if o.place else None,
        )
        for o in offers
    ]


@router.post("/special-offers", response_model=SpecialOfferWithPlace)
def create_special_offer(
    payload: SpecialOfferCreate,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> SpecialOfferWithPlace:
    """Создать спецпредложение."""
    if payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=400, detail="Дата начала не может быть позже даты окончания")

    place = db.execute(
        select(Place).where(
            Place.place_id == payload.place_id,
            Place.business_id == current_partner.id,
        )
    ).scalars().first()
    if place is None:
        raise HTTPException(
            status_code=404, detail="Место не найдено или не принадлежит партнёру")

    offer = SpecialOffer(
        place_id=payload.place_id,
        business_id=current_partner.id,
        title=payload.title,
        description=payload.description,
        discount_percent=payload.discount_percent,
        special_price=payload.special_price,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    db.refresh(place)

    return SpecialOfferWithPlace(
        id=offer.id,
        place_id=offer.place_id,
        business_id=offer.business_id,
        title=offer.title,
        description=offer.description,
        discount_percent=float(
            offer.discount_percent) if offer.discount_percent is not None else None,
        special_price=offer.special_price,
        start_date=offer.start_date,
        end_date=offer.end_date,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
        place_name=place.name or "",
        place_location=place.location,
        place_price=place.price,
    )


@router.put("/special-offers/{offer_id}", response_model=SpecialOfferWithPlace)
def update_special_offer(
    offer_id: int,
    payload: SpecialOfferUpdate,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> SpecialOfferWithPlace:
    """Обновить спецпредложение."""
    stmt = (
        select(SpecialOffer)
        .where(SpecialOffer.id == offer_id, SpecialOffer.business_id == current_partner.id)
        .options(joinedload(SpecialOffer.place))
    )
    offer = db.execute(stmt).scalars().first()
    if offer is None:
        raise HTTPException(
            status_code=404, detail="Спецпредложение не найдено")

    if payload.start_date is not None and payload.end_date is not None and payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=400, detail="Дата начала не может быть позже даты окончания")

    if payload.title is not None:
        offer.title = payload.title
    if payload.description is not None:
        offer.description = payload.description
    if payload.discount_percent is not None:
        offer.discount_percent = payload.discount_percent
    if payload.special_price is not None:
        offer.special_price = payload.special_price
    if payload.start_date is not None:
        offer.start_date = payload.start_date
    if payload.end_date is not None:
        offer.end_date = payload.end_date

    db.add(offer)
    db.commit()
    db.refresh(offer)
    place = offer.place

    return SpecialOfferWithPlace(
        id=offer.id,
        place_id=offer.place_id,
        business_id=offer.business_id,
        title=offer.title,
        description=offer.description,
        discount_percent=float(
            offer.discount_percent) if offer.discount_percent is not None else None,
        special_price=offer.special_price,
        start_date=offer.start_date,
        end_date=offer.end_date,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
        place_name=place.name if place else "",
        place_location=place.location if place else None,
        place_price=place.price if place else None,
    )


@router.delete("/special-offers/{offer_id}")
def delete_special_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> dict:
    """Удалить спецпредложение."""
    offer = db.execute(
        select(SpecialOffer).where(
            SpecialOffer.id == offer_id,
            SpecialOffer.business_id == current_partner.id,
        )
    ).scalars().first()
    if offer is None:
        raise HTTPException(
            status_code=404, detail="Спецпредложение не найдено")
    db.delete(offer)
    db.commit()
    return {"ok": True}
