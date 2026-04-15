# Bot Personas

Six playable bot personalities inspired by the Pokémon XY anime (Kalos region). Each persona maps to a difficulty tier and is expressed as a set of `persona_params` stored in the DB and forwarded to the engine at query time. The bot has no awareness of team assignment or game context beyond what is in the state — team-side constraints (e.g. Team Rocket always plays Blue) are enforced by the backend.

---

## How Personas Work

Each bot row in the DB carries a `params` JSONB column. When the backend triggers a bot move, it forwards `params` (with a load-adjusted `time_budget`) to the engine's `POST /move` endpoint as `persona_params`. The engine reads those params to configure the MCTS instance for that request.

**Relevant MCTS parameters:**

| Param | Effect |
|---|---|
| `time_budget` | Seconds of MCTS search per move — primary difficulty knob |
| `exploration_c` | UCB1 exploration constant. Higher → more random exploration; lower → ruthless exploitation of known-good lines |
| `use_transposition` | Whether the bot draws on / contributes to the global inter-game transposition table |
| `move_bias` | Optional behavioral bias: adds a UCB1 score bonus to matching moves throughout the search |

**Move bias** adds a small constant bonus to the UCB1 score of matching child nodes every time `select_child` is called. Because UCB1 governs which branches receive additional rollouts throughout the entire search, biased moves accumulate more visits and are structurally preferred at move selection time. The bonus is computed once at node expansion (from the move + parent state) and stored on the node permanently, so it is applied on every selection pass for the node's lifetime — not just at first expansion. C++ rollouts remain uniformly random; the bias operates through tree selection, not simulation policy.

---

## The Six Personas

### 1. Bonnie
*"She wants to find Clemont a wife, but maybe she should start by learning the rules."*

**Difficulty:** Easiest

Bonnie is the youngest trainer in the Kalos crew and very much a beginner. She gets the least thinking time and no access to the transposition table, so she can't draw on positional knowledge from past games. Her high exploration constant means she wanders into unusual, often suboptimal lines.

| Param | Value |
|---|---|
| `time_budget` | `0.5s` |
| `exploration_c` | `2.5` |
| `use_transposition` | `false` |
| `move_bias` | — |

---

### 2. Team Rocket
*"Prepare for trouble — and make it double!"*

**Difficulty:** Easy

Jessie, James, and Meowth are after one thing: Pikachu. They always play as Blue (so they're hunting Red's Pikachu) and their expansion bias aggressively prioritizes any move that attacks Pikachu or Raichu. They still bumble — low budget, no TT, and a high exploration constant ensure they're erratic — but they will fixate on the king in a way that makes them feel characterful. When Pikachu isn't immediately attackable, the bias has no moves to prefer and they play randomly, which also fits.

| Param | Value |
|---|---|
| `time_budget` | `1.0s` |
| `exploration_c` | `2.2` |
| `use_transposition` | `false` |
| `move_bias` | `chase_pikachu` |

**`chase_pikachu` bias:** ATTACK moves whose target is Pikachu or Raichu receive a persistent UCB1 score bonus. The bot will consistently allocate more of its search budget to those lines throughout the entire move decision.

---

### 3. Serena
*"Ash's rival. She's done her homework."*

**Difficulty:** Medium

Serena is a capable, well-rounded trainer. She has a full time budget to think, benefits from the transposition table, and plays with a default exploration constant — balanced between trying new things and playing what she knows works. No behavioral quirks; she just plays solid chess.

| Param | Value |
|---|---|
| `time_budget` | `2.0s` |
| `exploration_c` | `1.414` (√2) |
| `use_transposition` | `true` |
| `move_bias` | — |

---

### 4. Gym Leader Clemont
*"The future is now, thanks to science!"*

**Difficulty:** Medium-Hard

Clemont is Lumiose City's Electric-type Gym Leader and Bonnie's older brother. He always plays as Red (Electric gym, Pikachu is his piece to command) and his expansion bias favors moves originating from Pikachu or Raichu. He has a longer time budget than Serena and access to the TT, so his Pikachu-focused playstyle is also backed by real positional understanding — this isn't just a gimmick, it's a coherent strategy since Pikachu/Raichu have strong movement patterns.

| Param | Value |
|---|---|
| `time_budget` | `3.0s` |
| `exploration_c` | `1.414` (√2) |
| `use_transposition` | `true` |
| `move_bias` | `prefer_pikachu_raichu` |

**`prefer_pikachu_raichu` bias:** Moves originating from Pikachu or Raichu receive a persistent UCB1 score bonus. The bot will consistently allocate more of its search budget to lines involving those pieces throughout the entire move decision.

---

### 5. Champion Diantha
*"As the Pokémon Champion of the Kalos region, I take every battle seriously."*

**Difficulty:** Hard

Diantha is the strongest official trainer in Kalos. She gets a long time budget, full TT access, and a low exploration constant — she exploits what she knows works rather than experimenting. Playing her feels like facing a coherent, experienced opponent with deep positional awareness. No gimmicks, just strong play.

| Param | Value |
|---|---|
| `time_budget` | `5.0s` |
| `exploration_c` | `1.0` |
| `use_transposition` | `true` |
| `move_bias` | — |

---

### 6. METALLIC
*"...no one knows where this trainer came from. Some say they aren't real."*

**Difficulty:** Maximum

METALLIC is the secret final boss. Maximum time budget, full TT access, and an extremely low exploration constant mean METALLIC almost never experiments — it plays the move it believes is best, every time, with ruthless consistency. The name and lore are deliberately cryptic. Beat METALLIC and you've beaten the game.

| Param | Value |
|---|---|
| `time_budget` | `10.0s` |
| `exploration_c` | `0.5` |
| `use_transposition` | `true` |
| `move_bias` | — |

---

## Difficulty Summary

| # | Persona | Budget | TT | `exploration_c` | Bias |
|---|---|---|---|---|---|
| 1 | Bonnie | 0.5s | No | 2.5 | — |
| 2 | Team Rocket | 1.0s | No | 2.2 | `chase_pikachu` |
| 3 | Serena | 2.0s | Yes | 1.414 | — |
| 4 | Clemont | 3.0s | Yes | 1.414 | `prefer_pikachu_raichu` |
| 5 | Diantha | 5.0s | Yes | 1.0 | — |
| 6 | METALLIC | 10.0s | Yes | 0.5 | — |
