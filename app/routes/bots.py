from __future__ import annotations

from fastapi import APIRouter

from ..auth import Db
from ..schemas import BotOut

router = APIRouter(prefix="/bots", tags=["bots"])


@router.get("", response_model=list[BotOut])
async def list_bots(db: Db):
    rows = await db.fetch(
        """
        SELECT id, name,
               params->>'label'        AS label,
               params->>'flavor'       AS flavor,
               (params->>'time_budget')::float AS time_budget
        FROM bots
        ORDER BY (params->>'time_budget')::float ASC
        """
    )
    return [BotOut(**dict(r)) for r in rows]
