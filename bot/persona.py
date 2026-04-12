"""
Bot persona definitions for PokeChess.

Each Persona captures the full set of MCTS parameters for one difficulty tier.
to_bot_params() serializes to the dict stored in bots.params and forwarded
as persona_params by the app layer on every bot move request.

See docs/bot_personas.md for design rationale and full character descriptions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Persona:
    name: str
    time_budget: float
    exploration_c: float
    use_transposition: bool
    move_bias: Optional[str] = None
    bias_bonus: float = 0.15

    def to_bot_params(self) -> dict:
        """Serialize to the dict stored in bots.params."""
        params: dict = {
            "time_budget": self.time_budget,
            "exploration_c": self.exploration_c,
            "use_transposition": self.use_transposition,
        }
        if self.move_bias is not None:
            params["move_bias"] = self.move_bias
            params["bias_bonus"] = self.bias_bonus
        return params


_SQRT2 = math.sqrt(2)

BONNIE = Persona(
    name="Bonnie",
    time_budget=0.5,
    exploration_c=2.5,
    use_transposition=False,
)

TEAM_ROCKET = Persona(
    name="Team Rocket",
    time_budget=1.0,
    exploration_c=2.2,
    use_transposition=False,
    move_bias="chase_pikachu",
)

SERENA = Persona(
    name="Serena",
    time_budget=2.0,
    exploration_c=_SQRT2,
    use_transposition=True,
)

CLEMONT = Persona(
    name="Clemont",
    time_budget=3.0,
    exploration_c=_SQRT2,
    use_transposition=True,
    move_bias="prefer_pikachu_raichu",
)

DIANTHA = Persona(
    name="Diantha",
    time_budget=5.0,
    exploration_c=1.0,
    use_transposition=True,
)

METALLIC = Persona(
    name="METALLIC",
    time_budget=10.0,
    exploration_c=0.5,
    use_transposition=True,
)

ALL_PERSONAS: list[Persona] = [BONNIE, TEAM_ROCKET, SERENA, CLEMONT, DIANTHA, METALLIC]
