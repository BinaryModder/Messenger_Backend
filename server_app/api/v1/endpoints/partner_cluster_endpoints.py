from __future__ import annotations

from uuid import uuid4

from api.deps import get_current_partner, get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models import Cluster
from models.business_rep_model import BusinessRepresentative
from schemas import ClusterCreate, ClusterResponse, ClusterUpdate
from services.text_sanitizer import sanitize_fields
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/partner/clusters", tags=["partner-clusters"])


def _generate_cluster_id() -> str:
    return f"cl_{uuid4().hex[:10]}"


@router.get("", response_model=list[ClusterResponse])
def list_partner_clusters(
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> list[ClusterResponse]:
    stmt = (
        select(Cluster)
        .where(Cluster.business_id == current_partner.id)
        .order_by(Cluster.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


@router.post("", response_model=ClusterResponse, status_code=status.HTTP_201_CREATED)
def create_cluster(
    payload: ClusterCreate,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> ClusterResponse:
    # AI-like local sanitizer (no external API)
    results = sanitize_fields(
        title=payload.title,
        meta=payload.meta,
        description=payload.description,
    )

    title = results["title"].sanitized if "title" in results else payload.title
    meta = results["meta"].sanitized if "meta" in results else payload.meta
    description = (
        results["description"].sanitized
        if "description" in results
        else payload.description
    )

    cluster = Cluster(
        id=_generate_cluster_id(),
        business_id=current_partner.id,
        title=title,
        meta=meta,
        description=description,
        status="pending",
    )
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


@router.get("/{cluster_id}", response_model=ClusterResponse)
def get_cluster(
    cluster_id: str,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> ClusterResponse:
    cluster = db.get(Cluster, cluster_id)
    if cluster is None or cluster.business_id != current_partner.id:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


@router.put("/{cluster_id}", response_model=ClusterResponse)
def update_cluster(
    cluster_id: str,
    payload: ClusterUpdate,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> ClusterResponse:
    cluster = db.get(Cluster, cluster_id)
    if cluster is None or cluster.business_id != current_partner.id:
        raise HTTPException(status_code=404, detail="Cluster not found")

    results = sanitize_fields(
        title=payload.title if payload.title is not None else cluster.title,
        meta=payload.meta if payload.meta is not None else cluster.meta,
        description=payload.description
        if payload.description is not None
        else cluster.description,
    )

    if payload.title is not None:
        cluster.title = results["title"].sanitized
    if payload.meta is not None:
        cluster.meta = results["meta"].sanitized
    if payload.description is not None:
        cluster.description = results["description"].sanitized

    # After AI sanitization, return to pending
    cluster.status = "pending"

    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


@router.post("/{cluster_id}/approve", response_model=ClusterResponse)
def approve_cluster(
    cluster_id: str,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> ClusterResponse:
    cluster = db.get(Cluster, cluster_id)
    if cluster is None or cluster.business_id != current_partner.id:
        raise HTTPException(status_code=404, detail="Cluster not found")

    cluster.status = "approved"
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


@router.delete("/{cluster_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cluster(
    cluster_id: str,
    db: Session = Depends(get_db),
    current_partner: BusinessRepresentative = Depends(get_current_partner),
) -> None:
    cluster = db.get(Cluster, cluster_id)
    if cluster is None or cluster.business_id != current_partner.id:
        raise HTTPException(status_code=404, detail="Cluster not found")

    db.delete(cluster)
    db.commit()
    return None
