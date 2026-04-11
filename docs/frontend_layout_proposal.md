# PokeChess — Frontend Layout Proposal

**Audience:** 8–15 year olds  
**Target platform:** Tablet and phone (portrait and landscape). Desktop will work but is not the primary design target.  
**Last updated:** April 2026  

---

## Design Foundation

**Visual language:** Dark-field Pokemon aesthetic — deep navy/dark-purple background (carrying the existing `BG = (18, 20, 30)` tone from `pokechess_ui.py`), punchy accent colors, and Pokemon Gen-1 sprite art. The board itself is the visual hero; everything else is secondary. Typography should lean toward a rounded, bold sans-serif (e.g. "Nunito" or "Fredoka One") — friendly and readable for 8–15 year olds without feeling babyish.

**Color palette:**

| Token | Hex | Usage |
|---|---|---|
| `bg-deep` | `#12141E` | Page background |
| `bg-panel` | `#191B26` | Sidebar / card backgrounds |
| `bg-card` | `#232638` | Piece info cards, list items |
| `red-team` | `#E03737` | Pikachu / Red player |
| `blue-team` | `#3C72E0` | Eevee / Blue player |
| `hl-select` | `#64A0FF` | Selected piece ring |
| `hl-move` | `#F5E028` | Legal move squares |
| `hl-attack` | `#F55A19` | Attack target squares |
| `hl-foresight` | `#32D7FA` | Foresight target (Mew attack) |
| `hl-trade` | `#A855F7` | Trade target |
| `accent-gold` | `#FFD700` | XP, win screens, highlights |
| `type-water` | `#5EAEFF` | Type badges |
| `type-fire` | `#FF6B35` | Type badges |
| `type-grass` | `#4CAF50` | Type badges |
| `type-psychic` | `#E040FB` | Type badges |
| `type-electric` | `#FFD600` | Type badges |
| `type-normal` | `#BDBDBD` | Type badges |

---

## Pages

### 1. Home Screen

**Purpose:** Entry point. Two primary actions. No clutter.

**Layout (full-screen, centered):**
```
┌─────────────────────────────────────────┐
│  [animated Pokemon silhouettes drift    │
│   across the bg — Pikachu left,         │
│   Eevee right, facing each other]       │
│                                         │
│         ♟ POKECHESS                     │
│    [logo: Pokeball with chess knight]   │
│                                         │
│      [ ▶  Play vs Bot  ]               │
│      [    Play vs Friend ]              │
│                                         │
│         [My Pokemon]  [Settings]        │
└─────────────────────────────────────────┘
```

- **Play vs Bot** → large primary button (red-team color, since Red moves first against the bot), routes to difficulty selection → game creation via `POST /games` with `{ bot_id: <uuid>, player_side: "red" | "blue" }`
- **Play vs Friend** → secondary button (blue-team), routes to the invite/friends flow — **required for v1**
- **My Pokemon** → small text link to roster page
- **Settings** → small icon/text link
- Background: subtle animated particle field or looping sprite drift — not distracting, just alive

---

### 2. My Pokemon (Roster)

**Purpose:** Show all of the player's named Pokemon pieces, their species, XP, and held items. There are more than 5 — each piece role (both Rooks, both Knights, both Bishops, the Queen, and the King) is its own named Pokemon. Read-only in v1.

**Layout (scrollable card list):**
```
┌──────────────────────────────────────┐
│  ← Back          My Pokemon          │
├──────────────────────────────────────┤
│  ┌──────┐  Squirtle #1               │
│  │ 💧🔵 │  Water  ████████░░  Lv 12  │
│  └──────┘  Item: Waterstone          │
│  ┌──────┐  Squirtle #2               │
│  │ 💧🔵 │  Water  ███░░░░░░░  Lv 4   │
│  └──────┘  Item: Waterstone          │
│  ┌──────┐  Charmander #1             │
│  │ 🔥🔴 │  Fire   ███░░░░░░░  Lv 4   │
│  └──────┘  Item: Firestone           │
│  ... (full roster, scrollable)       │
└──────────────────────────────────────┘
```

- Each card: circular sprite chip (team-color ring + dark inner circle + sprite, matching board style), species name, type badge, XP progress bar, held item icon
- Pieces of the same species are differentiated by index (Squirtle #1, Squirtle #2)
- No editing controls in v1 — pure display
- Cards animate in on mount (slide up, stagger)

---

### 3. Difficulty Selection (PvB only)

**Purpose:** Shown after tapping "Play vs Bot" before the game is created. Simple one-tap choice.

**Layout:**
```
┌──────────────────────────────────────┐
│  ← Back     Choose Difficulty        │
├──────────────────────────────────────┤
│                                      │
│   [ Easy   ]   Metallic is sleepy    │
│   [ Medium ]   Metallic woke up      │
│   [ Hard   ]   Metallic means it     │
│   [ Expert ]   Metallic is scary     │
│   [ Master ]   Good luck...          │
│                                      │
└──────────────────────────────────────┘
```

Each option maps to a MCTS time budget sent as `time_budget` in the `POST /move` engine request:

| Difficulty | Time budget | Flavour text |
|---|---|---|
| Easy | 0.5s | Metallic is sleepy |
| Medium | 1.5s | Metallic woke up |
| Hard | 3.0s | Metallic means it |
| Expert | 5.0s | Metallic is scary |
| Master | 10.0s | Good luck... |

Tapping a difficulty immediately creates the game (no extra confirm step). Metallic is the name of the PvB bot — Team Alpha's artificial intelligence.

---

### 4. Game Lobby / Waiting Screen

**Purpose:** Shown while the server creates the game (PvB) or while waiting for a friend to accept an invite (PvP).

**PvB layout:**
```
┌──────────────────────────────────────┐
│                                      │
│    [Pikachu sprite, bouncing]        │
│                                      │
│      Setting up your game...         │
│      ████████████░░░░░░  (progress)  │
│                                      │
│      [Cancel]                        │
│                                      │
└──────────────────────────────────────┘
```

**PvP layout** (waiting for opponent to accept invite):
```
┌──────────────────────────────────────┐
│                                      │
│   [your avatar]    vs   [? pulsing]  │
│                                      │
│   Waiting for Misty to accept...     │
│                                      │
│   Share code:  PKC-4729              │
│   [Copy link]                        │
│                                      │
│   [Cancel invite]                    │
│                                      │
└──────────────────────────────────────┘
```

PvP invite screen polls `GET /game-invites` or listens for a push notification until the invitee accepts.

---

### 5. Gameplay Screen

**This is the most complex screen. The layout handles: board, piece info, turn status, HP, special move disambiguation, stored-in-ball display, and Foresight — without overwhelming the player.**

#### Overall Layout (tablet/phone — primary target ~390×844 portrait, ~844×390 landscape)

**Portrait (primary):**
```
┌─────────────────────────────┐
│ [BLUE banner]               │
│ Team Blue  HP:████░  Turn14 │
├─────────────────────────────┤
│                             │
│        8×8 Board            │
│     (full-width, square)    │
│                             │
├─────────────────────────────┤
│ [contextual bottom drawer]  │
│ Selected piece / last move  │
│ Legend  [collapse ▲]        │
├─────────────────────────────┤
│ [RED banner]                │
│ Team Red   HP:████████      │
│            [Your Turn!]     │
└─────────────────────────────┘
```

**Landscape (secondary):**
```
┌──────────────────────────────────────────────────────────┐
│ [BLUE banner] Team Blue  HP:████░  Turn 14  ⏱ Metallic…  │
├──────────────────────────────┬───────────────────────────┤
│                              │ Selected Piece Info        │
│       8×8 Board              │ ┌─────────────────────┐   │
│                              │ │[sprite] Squirtle #1 │   │
│   (dominant center)          │ │Water  HP: 80/200    │   │
│                              │ │████████░░           │   │
│                              │ │Item: Waterstone     │   │
│                              │ └─────────────────────┘   │
│                              │ Legend                     │
│                              │ 🟡Move  🟠Attack           │
│                              │ 🔵Select 🩵Foresight 🟣Trade│
│                              │ Last Move                  │
│                              │ "Charmander attacked       │
│                              │  Bulbasaur — 2× dmg!"      │
├──────────────────────────────┴───────────────────────────┤
│ [RED banner]   Team Red      HP: ████████   [Your Turn!] │
└──────────────────────────────────────────────────────────┘
```

In portrait, the contextual info (selected piece, legend, last move) lives in a collapsible **bottom drawer** that the player can swipe up. It defaults to a compact 1-line "last move" peek; swipe reveals the full card. This keeps the board as large as possible on small screens.

#### Board (center, dominant)

- 8×8 grid, squares ~72–80px each
- Light squares: warm cream `#EBF0CE`, dark squares: Pokemon-green `#6E8F52`
- Pieces: circular chip style from the demo — team-color outer ring (6px), dark inner circle, sprite centered
- HP shown as a thin colored arc on the piece ring (a "health halo"). Full = green, half = yellow, low = blinking red. Keeps the cell clean while giving HP at a glance.
- **Highlights on click:**
  - Selected piece: bright blue pulsing ring around the cell
  - Legal move squares: yellow semi-transparent overlay + small dot in center
  - Legal attack squares: orange semi-transparent overlay + crosshair dot
  - Foresight target (Mew attack): cyan glow overlay
  - Trade squares: purple overlay

#### Stored-in-Ball Display (Safetyball / Master Safetyball)

When a Safetyball has a Pokemon stored inside (`stored_piece` is non-null in game state):
- Show a small sprite badge of the stored Pokemon in the bottom-right corner of the Safetyball's cell, circle-clipped and ~20px
- The badge has a soft white glow border to distinguish it from the board square
- On hover/tap of the Safetyball, the right sidebar shows both the Safetyball and the stored Pokemon's info in a stacked card layout:

```
┌──────────────────────────────┐
│ Safetyball (empty carrier)   │
│ ──────────────────────────── │
│ [sprite]  Bulbasaur #2       │
│ Grass   HP: 140/200  (stored)│
│ ████████████░░░░░░           │
└──────────────────────────────┘
```

#### Top/Bottom Banners

- One banner per team, pinned top (Blue) and bottom (Red)
- Contains: "Team Red" / "Team Blue" label, King's HP bar (wide, prominent), active turn indicator
- **Metallic's turn state (PvB):** replace "Your Turn!" with a spinning Pokeball + "Metallic is thinking…" text; board squares subtly dim (50% opacity overlay) so the player knows not to tap. The wait can be up to 10s at Master difficulty — the animation must feel alive, not frozen.

#### Right Sidebar — Contextual Info

- **Selected Piece card** (appears on click): larger sprite, name, index (#1/#2), type badge, HP bar, held item. Disappears when nothing is selected.
- **Move Legend**: always visible, five color swatches with one-word labels. Serves as a permanent reminder for new players.
- **Last Move log**: single line, human-readable string of the most recent move event. Uses type color in the text ("Super Effective!" in orange, "Not Very Effective" in gray). Not a scrollable history — just the last event.

#### Special Move Disambiguation (Mew and Eevee Evolution)

When the API returns multiple moves sharing the same target square, a **bottom-sheet picker** slides up ~200px from the bottom of the board. It never covers the full board.

**Mew attack picker** (up to 3 attack types + Foresight as one of the options):
```
┌─────────────────────────────────────┐
│  Choose Mew's attack:               │
│                                     │
│  [🔥 Fire Blast]  [💧 Hydro Pump]   │
│  [🌿 Solar Beam]  [🩵 Foresight]    │
│                                     │
│  [Cancel]                           │
└─────────────────────────────────────┘
```

Foresight is listed here as one of Mew's attack options (or Espeon's), not as a separate action type. Its cyan color distinguishes it in the picker. Selecting it works like any other attack — the cyan highlight on the board shows the pending target.

**Eevee evolution picker** (up to 5 choices):
```
┌─────────────────────────────────────────────┐
│  What will Eevee evolve into?               │
│                                             │
│  [Vaporeon💧] [Flareon🔥] [Leafeon🌿]       │
│  [Jolteon⚡]  [Espeon🔮]                    │
│                                             │
│  [Cancel]                                   │
└─────────────────────────────────────────────┘
```

The Eevee evolution picker gets a slightly elevated treatment: golden border on the sheet, small sparkle CSS animation on each evolution option. This is a memorable in-game moment and should feel exciting.

#### Pokeball RNG Animation

After a Pokeball attack, before rendering the updated board state:
1. Show a 1–1.5s Pokeball wiggle animation over the target square (ball bounces and shakes)
2. Snap to result: piece disappears if `captured: true`, reappears with a small flash if `captured: false` (escaped)

The outcome is already resolved server-side; this is purely cosmetic timing to make the randomness feel alive rather than abrupt.

#### Foresight (Pending State)

When `pending_foresight` is non-null in the game state for either team:
- That target square always shows the cyan glow overlay, even when no piece is selected — a persistent reminder that a hit is incoming
- Small ghost/eye icon badge in the corner of that cell
- When `foresight_resolve` appears in the move history, flash that square + update "Last Move" to show the damage

#### Quick Attack (Eevee / Espeon)

Quick Attack requires selecting an attack target and then a post-attack move destination. Two-step flow:
1. Player clicks the piece → attack squares (orange) and move squares (yellow) both appear
2. Player clicks an attack target → board dims; only the valid post-attack move squares remain highlighted
3. Player clicks a movement destination → move submits
4. A small "Step 1 of 2 — now pick where to move" hint appears in the right sidebar during step 2 so the player is never confused about what to do next

---

### 6. Game Over Screen

**Purpose:** Clear team win/loss result, XP earned per piece, prompt for next action.

**Layout (overlay on top of the final board state, semi-transparent dark background):**
```
┌──────────────────────────────────────────┐
│                                          │
│   🏆  TEAM RED WINS!                     │
│   [Victory banner in team color]         │
│                                          │
│   [Pikachu / winning King sprite,        │
│    animated — jumping or sparking]       │
│                                          │
│   XP Earned this game:                  │
│   Squirtle #1    +120 ⭐ ████████░░░     │
│   Charmander #1   +80 ⭐ █████░░░░░     │
│   Bulbasaur #2    +60 ⭐ ███░░░░░░░     │
│   ...                                    │
│   (scrollable if full roster is shown)   │
│                                          │
│   [ Play Again ]      [ Home ]           │
│                                          │
└──────────────────────────────────────────┘
```

- Banner reads **"Team Red Wins!"** or **"Team Blue Wins!"** — not the King's name
- XP section shows each named piece that participated, `xp_earned` for this game (= total damage dealt), and for non-king pieces a progress bar reflecting how close they are to the next evolution threshold
- **Kings (Pikachu / Eevee) and the Queen (Mew) show XP earned but no evolution progress bar.** Kings evolve mid-game only (transient); Mew has no evolution at all. Show a small note like "In-game evolution only" or "No evolution" in place of the progress bar so players aren't confused about why these pieces don't level up permanently.
- `xp_applied` vs `xp_earned` distinction: show a brief "Applying XP…" loading state before the bars animate filling, so the player sees the reward land visually
- XP formula is intentionally simple for v1 and expected to evolve — the display layer reads values from the API and does not re-implement the formula
- Two clear CTAs: rematch or go home

#### Post-Game Evolution Cutscene (Future, not v1)

Once XP thresholds trigger an evolution, play an interstitial cutscene after the game-over XP screen:

```
┌──────────────────────────────────────────┐
│                                          │
│   [white flash fills screen]             │
│                                          │
│   What? Charmander is evolving!          │
│                                          │
│   [Charmander sprite pulses and          │
│    grows into a white silhouette,        │
│    then resolves into Charizard]         │
│                                          │
│   Charmander evolved into Charizard!     │
│                                          │
│   [  OK  ]                              │
│                                          │
└──────────────────────────────────────────┘
```

- Plays once per evolving piece, sequentially if multiple pieces evolve in one game
- Faithful to the classic Pokemon evolution sequence: white-out flash, silhouette morph, name reveal
- Music/sound sting if audio is in scope
- After all cutscenes play, the "Play Again / Home" buttons reappear

---

## UX Principles Applied

| Problem | Solution |
|---|---|
| Kids don't know chess notation | No algebraic notation anywhere — everything is visual highlight on the board |
| Too many possible actions | Right sidebar is fully contextual — only appears on click, shows only relevant info |
| Bot latency (up to 3s per move) | Explicit "Bot thinking…" spinner + board grayout — no ambiguity about whose turn it is |
| Stochastic Pokeball outcome | Brief ball-wiggle animation before result reveal — makes randomness feel exciting |
| Mew / Eevee multi-option moves | Bottom-sheet picker — preserves board context, minimal taps |
| Foresight is invisible between turns | Persistent cyan glow + eye badge on target square while pending |
| HP is critical but clutters the board | Thin HP arc on the piece ring (always visible) + full bar in sidebar on selection |
| Stored Pokemon inside a Safetyball | Small sprite badge on the ball's cell + stacked card in sidebar on hover |
| Roster has more than 5 Pokemon | Scrollable card list, indexed by species number (#1, #2) |
| Captured pieces state not in API | Captured pieces panel removed — not shown anywhere |
| Evolution is a special moment | Flashy bottom-sheet picker for in-game evolution; post-game cutscene for XP-triggered evolution |

---

## Resolved Decisions

| # | Question | Decision |
|---|---|---|
| Q1 | Mew / Eevee multi-option move UI | Bottom-sheet picker. Mew: up to 4 options (3 attacks + Foresight). Eevee: 5 evolution sprites. |
| Q2 | PvP scope | **PvP is in scope for v1.** Play vs Friend is a hard requirement. Friends + invite endpoints ship in v1. |
| Q3 | Move response contract | Single GameDetail payload. "Metallic is thinking…" state (spinning Pokeball, dimmed board) covers wait time. |
| Q4 | Legal moves in GameDetail | **Kept separate.** `GET /games/{id}/legal_moves` remains its own endpoint. GameDetail never embeds legal moves. |
| Q5 | XP formula | XP = damage dealt by that piece this game. Display reads values from API — formula lives server-side only. |
| Q6 | King/Queen evolution persistence | **Kings and Queen never persistently evolve.** Pikachu/Eevee always start fresh each game (in-game evolution only); Mew has no evolution. XP is tracked for all three but no evolution progress bar is shown. Only rooks, knights, and bishops evolve post-game. |
| Orientation | Primary target | Tablet and phone. Portrait is primary; landscape is secondary. Board fills width in portrait; collapsible bottom drawer for contextual info. |
| Difficulty | Selector levels | Easy (0.5s) / Medium (1.5s) / Hard (3s) / Expert (5s) / Master (10s). Selected before game creation. Flavour text per tier. |
| Sound | v1 scope | Simple sound effects in v1 (piece tap, move placement, attack hit, Pokeball shake, evolution sting, win/loss). Audio architecture must be extensible (volume controls, mute, easy asset swap) without blocking v1 delivery. Sound is a future-enhancement surface — do not let audio scope creep delay the core gameplay build. |

### Sound Architecture Note

Build with a thin audio manager abstraction from the start (e.g. a single `SoundManager` module with named slots: `play('piece_move')`, `play('attack_hit')`, etc.). v1 populates each slot with a simple sound file. Future versions can swap in richer effects, music, or voice without changing call sites. Keep the asset pipeline simple — a flat directory of `.mp3` / `.ogg` files, no complex audio graph needed for v1.
