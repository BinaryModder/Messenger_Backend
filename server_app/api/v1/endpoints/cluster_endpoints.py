"""Эндпоинт кластеров — группировка мест по типу для лендинга."""

from __future__ import annotations

from typing import List, Optional

from api.deps import get_db
from fastapi import APIRouter, Depends
from models import Cluster, Place
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

router = APIRouter(prefix="/clusters", tags=["clusters"])

# Названия кластеров по place_type (из seed)
CLUSTER_TITLES: dict[str, str] = {
    "cl1": "Отель и прогулки у моря",
    "cl2": "Дом среди природы",
    "cl3": "Локация для работы с видом",
    "cl4": "Винные маршруты и дегустации",
    "cl5": "Куда сходить с детьми",
    "cl6": "Нестандартная станица и ремесла",
}

# Координаты Краснодарского края по типу кластера
CLUSTER_COORDS: dict[str, dict[str, float]] = {
    "cl1": {"lat": 43.585, "lon": 39.723},  # побережье Сочи
    "cl2": {"lat": 45.041, "lon": 37.360},  # природа/озёра
    "cl3": {"lat": 44.982, "lon": 38.917},  # вид/работа
    "cl4": {"lat": 44.958, "lon": 37.783},  # вино, Анапа
    "cl5": {"lat": 45.025, "lon": 37.170},  # семейный
    "cl6": {"lat": 44.476, "lon": 39.016},  # станица
}


class PlaceInCluster(BaseModel):
    id: str
    photo: str
    rating: float
    title: str
    location: str
    lat: float
    lon: float
    fact: str
    cost: float
    description: str
    reviews_count: int
    avalin_tour_url: Optional[str] = None


class ClusterResponse(BaseModel):
    id: str
    coverImage: str
    title: str
    meta: str
    price: float
    rating: float
    reviews_count: int
    places: List[PlaceInCluster]


@router.get("", response_model=List[ClusterResponse])
def list_clusters(db: Session = Depends(get_db)) -> List[ClusterResponse]:
    """Возвращает кластеры (approved) для лендинга."""
    stmt = (
        select(Cluster)
        .where(Cluster.status == "approved")
        .options(
            joinedload(Cluster.places).joinedload(Place.images),
            joinedload(Cluster.places).selectinload(Place.reviews),
        )
        .order_by(Cluster.created_at.desc())
    )
    clusters = list(db.execute(stmt).unique().scalars().all())

    result: List[ClusterResponse] = []
    for cluster in clusters:
        plist = list(cluster.places or [])
        if not plist:
            continue

        coords = CLUSTER_COORDS.get(cluster.id, {"lat": 45.0, "lon": 38.0})
        meta = cluster.meta or "Краснодарский край"

        ratings = []
        total_reviews = 0
        place_items: List[PlaceInCluster] = []

        for p in plist:
            rev_count = len(p.reviews) if p.reviews else 0
            total_reviews += rev_count
            r = float(p.rating) if hasattr(p, "rating") and p.reviews else 4.8
            ratings.append(r)

            imgs = list(p.images) if p.images else []
            photo = imgs[0].image_url if imgs else ""

            place_items.append(
                PlaceInCluster(
                    id=f"{cluster.id}-p{p.place_id}",
                    photo=photo,
                    rating=r,
                    title=p.name or "",
                    location=p.location or "",
                    lat=coords["lat"],
                    lon=coords["lon"],
                    fact=p.interesting_fact or "",
                    cost=float(p.price or 0),
                    description=(p.description or p.description_ai or "")[:500],
                    reviews_count=rev_count,
                    avalin_tour_url=p.avalin_tour_url,
                )
            )

        avg_rating = sum(ratings) / len(ratings) if ratings else 4.8
        base_price = place_items[0].cost if place_items else 0
        cover = place_items[0].photo if place_items else ""

        result.append(
            ClusterResponse(
                id=cluster.id,
                coverImage=cover,
                title=cluster.title,
                meta=meta,
                price=round(base_price, 0),
                rating=round(avg_rating, 1),
                reviews_count=total_reviews,
                places=place_items,
            )
        )

    return result
