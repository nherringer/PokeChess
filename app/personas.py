"""
Persona display metadata for the PokeChess app layer.

This is distinct from bot/persona.py (MCTS operational parameters, engine container only).
This module holds UI-only data: difficulty stars, flavor text, accent colors, trainer
sprites, and forced player-side constraints. Keyed by the exact name column value in
the bots table.

bot/persona.py  → MCTS params (time_budget, exploration_c, …) — engine container
app/personas.py → Display metadata (stars, flavor, accent_color, …) — app container
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaDescriptor:
    name: str
    stars: int                      # 1–6 difficulty rank
    flavor: str                     # character quote shown on the persona card
    forced_player_side: str | None  # "red" | "blue" | None; lowercase, matches player_side convention
    accent_color: str               # CSS hex string, e.g. "#be2d2d"
    trainer_sprite: str             # filename in /sprites/trainers/, e.g. "teamrocket.png"


# Source of truth for all six personas.
# Values derived from pokechess_ui.py: PERSONA_STARS, PERSONA_FLAVOR (line 1),
# PERSONA_FORCED_PLAYER (lowercased), PERSONA_COLORS (converted to hex), PERSONA_SPRITE_FILE.
PERSONA_METADATA: dict[str, PersonaDescriptor] = {
    "Bonnie": PersonaDescriptor(
        name="Bonnie",
        stars=1,
        flavor="I'll take care of you! Dedenne, let's go!",
        forced_player_side=None,
        accent_color="#64d25a",
        trainer_sprite="bonnie.png",
    ),
    "Team Rocket": PersonaDescriptor(
        name="Team Rocket",
        stars=2,
        flavor="Prepare for trouble! We'll snatch your Pikachu!",
        forced_player_side="red",   # bot hunts Pikachu → player must hold Pikachu (RED)
        accent_color="#be2d2d",
        trainer_sprite="teamrocket.png",
    ),
    "Serena": PersonaDescriptor(
        name="Serena",
        stars=3,
        flavor="A true performer never shows weakness. En garde.",
        forced_player_side=None,
        accent_color="#5a96e6",
        trainer_sprite="serena.png",
    ),
    "Clemont": PersonaDescriptor(
        name="Clemont",
        stars=4,
        flavor="The science of my strategy is PERFECT! I guarantee it!",
        forced_player_side="blue",  # bot plays Pikachu side (RED) → player is BLUE
        accent_color="#e6c32d",
        trainer_sprite="clemont.png",
    ),
    "Diantha": PersonaDescriptor(
        name="Diantha",
        stars=5,
        flavor="I look forward to seeing what you can do. Truly.",
        forced_player_side=None,
        accent_color="#b955e1",
        trainer_sprite="diantha-masters.png",
    ),
    "METALLIC": PersonaDescriptor(
        name="METALLIC",
        stars=6,
        flavor="MATCH INITIATED. OUTCOME PREDETERMINED. RESISTANCE FUTILE.",
        forced_player_side=None,
        accent_color="#c3cddc",
        trainer_sprite="METALLIC.jpg",
    ),
}

# Fallback for any DB row whose name is not in PERSONA_METADATA (e.g. legacy rows).
_FALLBACK = PersonaDescriptor(
    name="Unknown",
    stars=1,
    flavor="",
    forced_player_side=None,
    accent_color="#888888",
    trainer_sprite="",
)


def get_persona(name: str) -> PersonaDescriptor:
    """Return the PersonaDescriptor for the given bot name, or a safe fallback."""
    return PERSONA_METADATA.get(name, _FALLBACK)
