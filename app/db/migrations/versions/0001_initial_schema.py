"""Initial schema — all tables, indexes, constraints, seed data.

Revision ID: 0001
Revises:
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    -- ===== users =====
    CREATE TABLE users (
        id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        username      VARCHAR     UNIQUE NOT NULL,
        email         VARCHAR     UNIQUE NOT NULL,
        password_hash VARCHAR     NOT NULL,
        created_at    TIMESTAMP   NOT NULL DEFAULT now()
    );

    -- ===== user_settings =====
    CREATE TABLE user_settings (
        user_id        UUID        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        board_theme    VARCHAR     NOT NULL DEFAULT 'classic',
        extra_settings JSONB       NOT NULL DEFAULT '{}',
        updated_at     TIMESTAMP
    );

    -- ===== friendships =====
    CREATE TABLE friendships (
        id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        user_a_id     UUID        NOT NULL REFERENCES users(id),
        user_b_id     UUID        NOT NULL REFERENCES users(id),
        initiator_id  UUID        NOT NULL REFERENCES users(id),
        status        VARCHAR     NOT NULL,
        created_at    TIMESTAMP   NOT NULL DEFAULT now(),

        CONSTRAINT friendships_order   CHECK (user_a_id::text < user_b_id::text),
        CONSTRAINT friendships_status  CHECK (status IN ('pending', 'accepted', 'rejected')),
        UNIQUE (user_a_id, user_b_id)
    );

    CREATE INDEX idx_friendships_a ON friendships (user_a_id);
    CREATE INDEX idx_friendships_b ON friendships (user_b_id);

    -- ===== bots =====
    CREATE TABLE bots (
        id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        name        VARCHAR     NOT NULL,
        params      JSONB       NOT NULL DEFAULT '{}',
        created_at  TIMESTAMP   NOT NULL DEFAULT now()
    );

    -- ===== game_invites =====
    CREATE TABLE game_invites (
        id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        inviter_id  UUID        NOT NULL REFERENCES users(id),
        invitee_id  UUID        NOT NULL REFERENCES users(id),
        status      VARCHAR     NOT NULL DEFAULT 'pending',
        created_at  TIMESTAMP   NOT NULL DEFAULT now(),

        CONSTRAINT invite_status CHECK (status IN ('pending', 'accepted', 'rejected', 'expired'))
    );

    -- ===== games =====
    CREATE TABLE games (
        id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        red_player_id   UUID        REFERENCES users(id),
        blue_player_id  UUID        REFERENCES users(id),
        is_bot_game     BOOLEAN     NOT NULL DEFAULT false,
        bot_id          UUID        REFERENCES bots(id),
        bot_side        VARCHAR,
        invite_id       UUID        REFERENCES game_invites(id),
        status          VARCHAR     NOT NULL DEFAULT 'pending',
        whose_turn      VARCHAR,
        turn_number     INT         NOT NULL DEFAULT 0,
        state           JSONB,
        move_history    JSONB       NOT NULL DEFAULT '[]',
        winner          VARCHAR,
        end_reason      VARCHAR,
        created_at      TIMESTAMP   NOT NULL DEFAULT now(),
        updated_at      TIMESTAMP   NOT NULL DEFAULT now(),

        CONSTRAINT game_status    CHECK (status IN ('pending', 'active', 'complete')),
        CONSTRAINT game_turn      CHECK (whose_turn IN ('red', 'blue')),
        CONSTRAINT game_winner    CHECK (winner IN ('red', 'blue', 'draw')),
        CONSTRAINT game_end       CHECK (end_reason IN ('king_eliminated', 'resign', 'timeout', 'draw')),
        CONSTRAINT bot_side_valid CHECK (bot_side IS NULL OR bot_side IN ('red', 'blue')),
        CONSTRAINT bot_consistency CHECK (
            (is_bot_game = false
                AND bot_id IS NULL AND bot_side IS NULL
                AND red_player_id IS NOT NULL AND blue_player_id IS NOT NULL)
            OR
            (is_bot_game = true
                AND bot_id IS NOT NULL AND bot_side IS NOT NULL
                AND num_nonnulls(red_player_id, blue_player_id) = 1)
        )
    );

    -- One active PvP game per player pair (order-independent)
    CREATE UNIQUE INDEX one_active_pvp
    ON games (
        LEAST(red_player_id::text, blue_player_id::text),
        GREATEST(red_player_id::text, blue_player_id::text)
    )
    WHERE status = 'active' AND is_bot_game = false;

    -- One active PvB game per human player per bot
    CREATE UNIQUE INDEX one_active_pvb
    ON games (COALESCE(red_player_id, blue_player_id), bot_id)
    WHERE status = 'active' AND is_bot_game = true;

    CREATE INDEX idx_games_red_active  ON games (red_player_id)  WHERE status = 'active';
    CREATE INDEX idx_games_blue_active ON games (blue_player_id) WHERE status = 'active';
    CREATE INDEX idx_games_red_done    ON games (red_player_id)  WHERE status = 'complete';
    CREATE INDEX idx_games_blue_done   ON games (blue_player_id) WHERE status = 'complete';

    -- ===== pokemon_pieces =====
    CREATE TABLE pokemon_pieces (
        id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        owner_id         UUID        NOT NULL REFERENCES users(id),
        role             VARCHAR     NOT NULL,
        species          VARCHAR     NOT NULL,
        xp               INT         NOT NULL DEFAULT 0,
        evolution_stage   INT         NOT NULL DEFAULT 0,
        created_at       TIMESTAMP   NOT NULL DEFAULT now(),

        CONSTRAINT piece_role CHECK (role IN ('king', 'queen', 'rook', 'bishop', 'knight'))
    );

    -- ===== game_pokemon_map =====
    CREATE TABLE game_pokemon_map (
        id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        game_id           UUID        NOT NULL REFERENCES games(id),
        pokemon_piece_id  UUID        NOT NULL REFERENCES pokemon_pieces(id),
        xp_earned         INT         NOT NULL DEFAULT 0,
        xp_applied        INT         NOT NULL DEFAULT 0,
        xp_applied_at     TIMESTAMP,
        xp_skip_reason    VARCHAR,

        UNIQUE (game_id, pokemon_piece_id)
    );

    CREATE INDEX idx_gpm_unapplied ON game_pokemon_map (game_id)
    WHERE xp_applied_at IS NULL;

    -- ===== Seed bot: Metallic =====
    INSERT INTO bots (name, params) VALUES (
        'Metallic',
        '{"time_budget": 1.0, "iteration_budget": null}'::jsonb
    );
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS game_pokemon_map CASCADE;
    DROP TABLE IF EXISTS pokemon_pieces CASCADE;
    DROP TABLE IF EXISTS games CASCADE;
    DROP TABLE IF EXISTS game_invites CASCADE;
    DROP TABLE IF EXISTS bots CASCADE;
    DROP TABLE IF EXISTS friendships CASCADE;
    DROP TABLE IF EXISTS user_settings CASCADE;
    DROP TABLE IF EXISTS users CASCADE;
    """)
