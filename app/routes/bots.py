from __future__ import annotations

from fastapi import APIRouter

from ..auth import Db
from ..personas import get_persona
from ..schemas import BotOut

router = APIRouter(prefix="/bots", tags=["bots"])


@router.get("", response_model=list[BotOut])
async def list_bots(db: Db):
    rows = await db.fetch(
        """
        SELECT id, name,
               COALESCE((params->>'time_budget')::float, 3.0) AS time_budget
        FROM bots
        ORDER BY COALESCE((params->>'time_budget')::float, 3.0) ASC
        """
    )
    result = []
    for r in rows:
        p = get_persona(r["name"])
        result.append(BotOut(
            id=r["id"],
            name=r["name"],
            stars=p.stars,
            flavor=p.flavor,
            forced_player_side=p.forced_player_side,
            accent_color=p.accent_color,
            trainer_sprite=p.trainer_sprite,
            time_budget=r["time_budget"],
        ))
    return result
