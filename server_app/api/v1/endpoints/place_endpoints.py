from __future__ import annotations

from typing import List, Optional

from api.deps import get_current_partner, get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from models import Cluster, Place, PlaceImage
from models.business_rep_model import BusinessRepresentative
from schemas import (
    PlaceCreate,
    PlaceDetailResponse,
    PlaceResponse,
    PlaceReviewResponse,
    PlaceUpdate,
)
from services.text_sanitizer import sanitize_fields
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

router = APIRouter(prefix="/places", tags=["places"])


def _final_description(place: Place) -> Optional[str]:
    # Если модератор не переписал - показываем AI-версию
    if place.description is not None and place.description != "":
        return place.description
    return place.description_ai


def _calc_rating(place: Place) -> float:
    if not place.reviews:
        return 0.0
    return float(sum(r.rating for r in place.reviews)) / float(len(place.reviews))


def _place_to_detail(place: Place) -> PlaceDetailResponse:
    rating = _calc_rating(place)
    reviews = [
        PlaceReviewResponse(
            tourist_id=r.tourist_id,
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
        )
        for r in (place.reviews or [])
    ]
    return PlaceDetailResponse(
        place_id=place.place_id,
        business_id=place.business_id,
        cluster_id=place.cluster_id,
        name=place.name,
        place_type=place.place_type,
        location=place.location,
        interesting_fact=place.interesting_fact,
        ai_link=place.ai_link,
        avalin_tour_url=place.avalin_tour_url,
        description_ai=place.description_ai,
        description=_final_description(place),
        price=place.price,
        created_at=place.created_at,
        images=[img.image_url for img in (place.images or [])],
        rating=rating,
        reviews=reviews,
    )


@router.post("", response_model=PlaceDetailResponse)
def create_place(
    payload: PlaceCreate,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> PlaceDetailResponse:
    if not payload.cluster_id:
        raise HTTPException(status_code=400, detail="cluster_id is required")

    cluster = db.get(Cluster, payload.cluster_id)
    if cluster is None or cluster.business_id != current_partner.id:
        raise HTTPException(status_code=404, detail="Cluster not found")

    results = sanitize_fields(
        title=payload.name,
        meta=payload.location,
        description=payload.description or payload.description_ai,
        interesting_fact=payload.interesting_fact,
    )
    name = results["title"].sanitized
    location = results["meta"].sanitized if payload.location is not None else None
    description = (
        results["description"].sanitized if payload.description is not None else None
    )
    description_ai = (
        results["description"].sanitized if payload.description_ai is not None else None
    )
    interesting_fact = (
        results["interesting_fact"].sanitized
        if payload.interesting_fact is not None
        else None
    )

    place = Place(
        business_id=current_partner.id,
        cluster_id=payload.cluster_id,
        name=name,
        place_type=payload.place_type or payload.cluster_id,
        location=location,
        interesting_fact=interesting_fact,
        ai_link=str(payload.ai_link) if payload.ai_link is not None else None,
        description_ai=description_ai,
        description=description,
        price=payload.price,
    )
    db.add(place)
    db.commit()
    db.refresh(place)

    if payload.images:
        db.add_all(
            [
                PlaceImage(place_id=place.place_id, image_url=url)
                for url in payload.images
            ]
        )
        db.commit()
        db.refresh(place)

    # place.images догрузится через relationship(lazy="joined") либо после refresh
    return _place_to_detail(place)


@router.put("/{place_id}", response_model=PlaceDetailResponse)
def update_place(
    place_id: int,
    payload: PlaceUpdate,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> PlaceDetailResponse:
    stmt = (
        select(Place)
        .where(Place.place_id == place_id, Place.business_id == current_partner.id)
        .options(joinedload(Place.images), selectinload(Place.reviews))
    )
    place = db.execute(stmt).scalars().first()
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")

    if payload.cluster_id is not None:
        cluster = db.get(Cluster, payload.cluster_id)
        if cluster is None or cluster.business_id != current_partner.id:
            raise HTTPException(status_code=404, detail="Cluster not found")
        place.cluster_id = payload.cluster_id
        place.place_type = payload.place_type or payload.cluster_id

    results = sanitize_fields(
        title=payload.name if payload.name is not None else place.name,
        meta=payload.location if payload.location is not None else place.location,
        description=payload.description
        if payload.description is not None
        else place.description,
        interesting_fact=payload.interesting_fact
        if payload.interesting_fact is not None
        else place.interesting_fact,
    )

    if payload.business_id is not None:
        place.business_id = payload.business_id
    if payload.name is not None:
        place.name = results["title"].sanitized
    if payload.place_type is not None and payload.cluster_id is None:
        place.place_type = payload.place_type
    if payload.location is not None:
        place.location = results["meta"].sanitized
    if payload.interesting_fact is not None:
        place.interesting_fact = results["interesting_fact"].sanitized
    if payload.ai_link is not None:
        place.ai_link = str(payload.ai_link)
    if payload.description_ai is not None:
        place.description_ai = payload.description_ai
    if payload.description is not None:
        place.description = results["description"].sanitized
    if payload.price is not None:
        place.price = payload.price

    # images: если images is not None -> заменяем полностью
    if payload.images is not None:
        place.images = []
        if payload.images:
            place.images = [
                PlaceImage(place_id=place_id, image_url=url) for url in payload.images
            ]

    db.add(place)
    db.commit()
    db.refresh(place)
    return _place_to_detail(place)


@router.get("", response_model=List[PlaceResponse])
def list_places(
    q: Optional[str] = Query(
        default=None, description="Поиск по названию/локации/факту"
    ),
    place_type: Optional[str] = Query(
        default=None, alias="type", description="Фильтр по типу места"
    ),
    db: Session = Depends(get_db),
) -> List[PlaceResponse]:
    stmt = (
        select(Place)
        .order_by(Place.created_at.desc())
        .options(joinedload(Place.images), selectinload(Place.reviews))
    )

    if q:
        q_like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Place.name.ilike(q_like),
                Place.location.ilike(q_like),
                Place.interesting_fact.ilike(q_like),
                Place.description_ai.ilike(q_like),
                Place.description.ilike(q_like),
            )
        )

    if place_type:
        stmt = stmt.where(func.lower(Place.place_type) == place_type.strip().lower())

    places = db.execute(stmt).unique().scalars().all()

    return [
        PlaceResponse(
            place_id=p.place_id,
            business_id=p.business_id,
            name=p.name,
            place_type=p.place_type,
            location=p.location,
            interesting_fact=p.interesting_fact,
            ai_link=p.ai_link,
            avalin_tour_url=p.avalin_tour_url,
            description_ai=p.description_ai,
            description=_final_description(p),
            price=p.price,
            created_at=p.created_at,
            images=[img.image_url for img in (p.images or [])],
            rating=_calc_rating(p),
        )
        for p in places
    ]


@router.post("/compute-embeddings")
def compute_all_place_embeddings(db: Session = Depends(get_db)):
    """
    ⚠️ DEPRECATED: DeepSeek не поддерживает embeddings API.
    
    Система использует локальный TF-IDF поиск автоматически.
    Embeddings в БД зарезервированы для будущей интеграции с:
    - OpenAI API (text-embedding-3-small)
    - Другими сервисами
    """
    from services.place_search_service import ensure_place_embedding

    stmt = select(Place).where(Place.embedding.is_(None))
    places = list(db.execute(stmt).scalars().all())
    total = len(places)
    
    # Пока не пытаемся вычислять - DeepSeek не поддерживает embeddings
    computed = 0
    
    return {
        "status": "deprecated",
        "message": "DeepSeek не поддерживает embeddings API. Используется локальный TF-IDF поиск.",
        "total_without_embedding": total,
        "computed": computed,
        "note": "Для использования embeddings настройте EMBEDDING_SERVICE=openai в .env"
    }


@router.get("/{place_id}", response_model=PlaceDetailResponse)
def get_place(place_id: int, db: Session = Depends(get_db)) -> PlaceDetailResponse:
    stmt = (
        select(Place)
        .where(Place.place_id == place_id)
        .options(joinedload(Place.images), selectinload(Place.reviews))
    )
    place = db.execute(stmt).scalars().first()
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    return _place_to_detail(place)


@router.post("/{place_id}/compute-embedding")
def compute_place_embedding(place_id: int, db: Session = Depends(get_db)):
    """
    ⚠️ DEPRECATED: DeepSeek не поддерживает embeddings API.
    
    Используется локальный TF-IDF поиск вместо embeddings.
    """
    stmt = select(Place).where(Place.place_id == place_id)
    place = db.execute(stmt).scalars().first()
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    
    return {
        "place_id": place_id,
        "embedding_computed": False,
        "status": "deprecated",
        "message": "DeepSeek не поддерживает embeddings API. Используется локальный TF-IDF.",
        "note": "Для embeddings используйте EMBEDDING_SERVICE=openai"
    }


@router.delete("/{place_id}")
def delete_place(
    place_id: int,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> dict:
    """Удалить место (вместе с изображениями, отзывами и спецпредложениями)."""
    place = (
        db.execute(
            select(Place).where(
                Place.place_id == place_id,
                Place.business_id == current_partner.id,
            )
        )
        .scalars()
        .first()
    )
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    db.delete(place)
    db.commit()
    return {"ok": True}
