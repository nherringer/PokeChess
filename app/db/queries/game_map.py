from __future__ import annotations

from uuid import UUID

import asyncpg


async def update_xp_earned(
    db: asyncpg.Connection,
    game_id: UUID,
    xp_by_piece: dict[str, int],
    winner_side: str | None,
    end_reason: str,
) -> None:
    """
    Write XP earned + applied for all pieces in this game.
    Called once at game completion.
    """
    for piece_id_str, earned in xp_by_piece.items():
        piece_id = UUID(piece_id_str)

        # Determine if XP should be applied (wins only for v1)
        # We need to know which side this piece is on
        row = await db.fetchrow(
            """
            SELECT gpm.id, pp.owner_id,
                   CASE
                     WHEN g.red_player_id = pp.owner_id THEN 'red'
                     WHEN g.blue_player_id = pp.owner_id THEN 'blue'
                   END AS player_side
            FROM game_pokemon_map gpm
            JOIN pokemon_pieces pp ON pp.id = gpm.pokemon_piece_id
            JOIN games g ON g.id = gpm.game_id
            WHERE gpm.game_id = $1 AND gpm.pokemon_piece_id = $2
            """,
            game_id,
            piece_id,
        )
        if row is None:
            continue

        player_side = row["player_side"]
        should_apply = winner_side == player_side
        skip_reason = None if should_apply else end_reason

        await db.execute(
            """
            UPDATE game_pokemon_map SET
                xp_earned = $3,
                xp_applied = CASE WHEN $4 THEN $3 ELSE 0 END,
                xp_applied_at = now(),
                xp_skip_reason = $5
            WHERE game_id = $1 AND pokemon_piece_id = $2
            """,
            game_id,
            piece_id,
            earned,
            should_apply,
            skip_reason,
        )

    # Roll up applied XP to pokemon_pieces
    await db.execute(
        """
        UPDATE pokemon_pieces p SET
            xp = p.xp + gpm.xp_applied,
            evolution_stage = CASE
                WHEN p.role IN ('king', 'queen') THEN 0
                WHEN (p.xp + gpm.xp_applied) >= 100 THEN 2
                WHEN (p.xp + gpm.xp_applied) >= 30  THEN 1
                ELSE p.evolution_stage
            END
        FROM game_pokemon_map gpm
        WHERE gpm.game_id = $1
          AND gpm.pokemon_piece_id = p.id
          AND gpm.xp_applied > 0
        """,
        game_id,
    )
