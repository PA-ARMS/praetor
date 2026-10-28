"""
Semantic response cache: persist query embeddings and answers; reuse on similar questions.
Lookup is per-user, scoped by RAG/detail/doc settings and Ollama model name.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy.orm import Session

from server.config import settings
from server.models import SemanticResponseCache
from server.utils.logger import setup_logger

logger = setup_logger("semantic_cache")


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def scope_fingerprint(
    use_rag: bool,
    exhaustive_search: bool,
    detail_level: str,
    max_results: int,
    doc_sources: Optional[List[str]],
    skip_clarification: bool,
    response_format: str = "research_memo",
    extra: str = "",
) -> str:
    parts = [
        "2",
        str(use_rag),
        str(exhaustive_search),
        detail_level or "standard",
        str(max_results),
        json.dumps(sorted(doc_sources or []), sort_keys=True),
        str(skip_clarification),
        response_format or "research_memo",
        extra or "",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


@dataclass
class CacheHit:
    row: SemanticResponseCache
    similarity: float


def find_best_match(
    db: Session,
    user_id: int,
    query_embedding: List[float],
    scope_fp: str,
    ollama_model: str,
) -> Optional[CacheHit]:
    if not settings.SEMANTIC_CACHE_ENABLED or not query_embedding:
        return None
    limit = max(10, min(settings.SEMANTIC_CACHE_MAX_CANDIDATES, 2000))
    rows: List[SemanticResponseCache] = (
        db.query(SemanticResponseCache)
        .filter(
            SemanticResponseCache.user_id == user_id,
            SemanticResponseCache.scope_fingerprint == scope_fp,
            SemanticResponseCache.ollama_model == ollama_model,
        )
        .order_by(SemanticResponseCache.created_at.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return None
    best: Optional[Tuple[SemanticResponseCache, float]] = None
    for row in rows:
        try:
            emb = json.loads(row.embedding_json)
            sim = _cosine_similarity(query_embedding, emb)
        except Exception:
            continue
        if best is None or sim > best[1]:
            best = (row, sim)
    if best is None:
        return None
    row, sim = best
    if sim < settings.SEMANTIC_CACHE_MIN_SIMILARITY:
        return None
    return CacheHit(row=row, similarity=sim)


def record_hit(db: Session, cache_id: int) -> None:
    row = db.query(SemanticResponseCache).filter(SemanticResponseCache.id == cache_id).first()
    if not row:
        return
    row.hit_count = (row.hit_count or 0) + 1
    row.last_hit_at = datetime.utcnow()
    db.commit()


def prune_user_cache(db: Session, user_id: int) -> None:
    max_n = settings.SEMANTIC_CACHE_MAX_PER_USER
    count = db.query(SemanticResponseCache).filter(SemanticResponseCache.user_id == user_id).count()
    if count <= max_n:
        return
    excess = count - max_n
    old_ids = [
        r.id
        for r in db.query(SemanticResponseCache)
        .filter(SemanticResponseCache.user_id == user_id)
        .order_by(SemanticResponseCache.created_at.asc())
        .limit(excess)
        .all()
    ]
    if old_ids:
        db.query(SemanticResponseCache).filter(SemanticResponseCache.id.in_(old_ids)).delete(
            synchronize_session=False
        )
        db.commit()


def store(
    db: Session,
    *,
    user_id: int,
    scope_fp: str,
    ollama_model: str,
    query_preview: str,
    query_embedding: List[float],
    response_text: str,
    sources_display: List[dict],
    full_sources: List[dict],
    warnings: List[str],
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    if not settings.SEMANTIC_CACHE_ENABLED or not query_embedding:
        return
    try:
        row = SemanticResponseCache(
            user_id=user_id,
            scope_fingerprint=scope_fp,
            ollama_model=ollama_model[:128],
            query_preview=(query_preview or "")[:2000],
            embedding_json=json.dumps(query_embedding),
            response_text=response_text,
            sources_display_json=json.dumps(sources_display),
            full_sources_json=json.dumps(full_sources),
            warnings_json=json.dumps(warnings or []),
            extra_json=json.dumps(extra) if extra else None,
            hit_count=0,
            last_hit_at=None,
        )
        db.add(row)
        db.commit()
        prune_user_cache(db, user_id)
    except Exception as e:
        db.rollback()
        logger.warning(f"Semantic cache store failed: {e}")


def deserialize_cached_response(row: SemanticResponseCache) -> Tuple[str, List[dict], List[dict], List[str], Dict[str, Any]]:
    sources_display = json.loads(row.sources_display_json or "[]")
    full_sources = json.loads(row.full_sources_json or "[]")
    warnings = json.loads(row.warnings_json or "[]")
    extra = json.loads(row.extra_json or "{}")
    return row.response_text, sources_display, full_sources, warnings, extra


class SemanticCacheService:
    """Namespace for chat route imports (matches ollama_service pattern)."""

    scope_fingerprint = staticmethod(scope_fingerprint)
    find_best_match = staticmethod(find_best_match)
    record_hit = staticmethod(record_hit)
    prune_user_cache = staticmethod(prune_user_cache)
    store = staticmethod(store)
    deserialize_cached_response = staticmethod(deserialize_cached_response)


semantic_cache_service = SemanticCacheService()
