# PokeChess — Frontend Layout Proposal

**Audience:** 8–15 year olds  
**Target platform:** Tablet and phone (portrait and landscape). Desktop will work but is not the primary design target.  
**Last updated:** April 2026 — wireframes below are the **design intent**; the **Implementation snapshot** subsection documents what the Next.js app actually routes today.

---

## Implementation snapshot (Next.js `frontend/`)

This is a concise map of **routes and shell behavior** on current development branches. Use it together with the page wireframes in §§1–8.

### App shell and auth

- **Root layout:** Dark full-height column, global styles from `globals.css`, Tailwind tokens in `tailwind.config.ts` (see §Design Foundation — note **`bg-deep` is `#0d0f1a` in code** vs `#12141E` in the table; treat as close cousins until unified).
- **`AuthInitializer`:** Hydrates the access token from `localStorage`; **redirects to `/login`** for any path that is not public (`/`, `/login`, `/register`) when logged out.
- **`AuthNav`:** Shown when authenticated — sticky top bar with small **PokeChess** logo (home → **`/my-pokemon`**), text links **My Pokémon**, **My Games**, **Play vs Bot**, **Friends**, and **Log out**. There is **no Settings link** in the nav yet (wireframe §1 still mentions Settings).

### Route map (App Router)

| Path | Purpose |
|------|---------|
| `/` | Guest **landing**: logo, starfield, Pikachu/Eevee art, **Register** / **Sign In**. If already logged in, **redirects to `/my-pokemon`** (differs from the single “home with Play vs Bot” wireframe). |
| `/login`, `/register` | Email/password auth; refresh cookie + Bearer token stored client-side. |
| `/my-pokemon` | Primary **post-login hub**: roster from `GET /users/me`, pieces shown as cards (back-rank ordering, sprites, type, XP). |
| `/roster` | Alternate roster view (role-ordered cards; same API data, different layout). |
| `/my-games` | **`GET /games`** — Active + Recent completed lists using **`GameListCard`**; linked from **AuthNav**. |
| `/games` | Same games list pattern as `/my-games` (secondary entry; may use `PageShell` with back). |
| `/play` | **PvB difficulty chooser**: `GET /bots`, then **`POST /games`** with `{ bot_id, player_side: "red" }` → navigates to **`/game/[id]`**. |
| `/play/lobby` | **PvB** short “setting up…” splash, or **PvP** inviter wait — query params `gameId` / `inviteId`; polls **`GET /game-invites`** until the game is active or invite ends. |
| `/friends` | Friends list, friend requests, **and** incoming game invites (challenge flow + invite accept — social hub). |
| `/game/[id]` | **Gameplay**: `GameBoard`, `TeamBanner` ×2, `BottomDrawer` (selected piece, legend, last move), disambiguation pickers (Mew / Pikachu / Eevee), `BotThinkingOverlay`, Pokeball wiggle, resign. Polls **`GET /games/{id}`** on a ~2.5s interval. |
| `/game/over` | **Game over** screen (`?gameId=`): team result, XP-style rows derived from move history client-side for display. |

### Divergences from wireframes (intentional or pending)

| Wireframe | Current app |
|-----------|-------------|
| §1 Single home with four CTAs | Split: **guest** landing (`/`) vs **authenticated** hub (`/my-pokemon`) + **AuthNav** for Play / Games / Friends. |
| §1 Settings | Not a dedicated routed page in nav yet. |
| §5 `GET /bots` “until implemented” | **`GET /bots` is implemented**; `/play` uses live bot rows (label, flavor, `time_budget`). |
| §6 Lobby | Exists as **`/play/lobby`**; PvB may transition quickly to the game route. |
| §8 Game over overlay | Also implemented as a **dedicated `/game/over`** route after terminal state. |

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
- **Friends** → small text link to the Friends screen (also accessible from the Friends screen itself)
- **Settings** → small icon/text link
- Background: subtle animated particle field or looping sprite drift — not distracting, just alive

---

### 2. Friends

**Purpose:** Find new friends by username, manage incoming/outgoing requests, and pick a friend to play against. This is the social hub and the required entry point before sending a game invite.

**Layout (tabbed, scrollable):**
```
┌──────────────────────────────────────┐
│  ← Back           Friends            │
├──────────────────────────────────────┤
│  🔍 Search by username or email...   │
│     [ ash_ketchum          ] [Add]   │
├──────────────────────────────────────┤
│  [ Friends ] [ Requests (2) ]        │
├──────────────────────────────────────┤
│  (Friends tab — default)             │
│  ┌─────────────────────────────────┐ │
│  │ 🟢 Misty         [Invite ▶]    │ │
│  └─────────────────────────────────┘ │
│  ┌─────────────────────────────────┐ │
│  │ 🟢 Brock         [Invite ▶]    │ │
│  └─────────────────────────────────┘ │
│  ┌─────────────────────────────────┐ │
│  │ ⚪ Gary           [Invite ▶]   │ │
│  └─────────────────────────────────┘ │
└──────────────────────────────────────┘
```

```
┌──────────────────────────────────────┐
│  (Requests tab)                      │
│                                      │
│  Incoming (2)                        │
│  ┌─────────────────────────────────┐ │
│  │ Jessie wants to be friends      │ │
│  │              [Accept] [Decline] │ │
│  └─────────────────────────────────┘ │
│  ┌─────────────────────────────────┐ │
│  │ James wants to be friends       │ │
│  │              [Accept] [Decline] │ │
│  └─────────────────────────────────┘ │
│                                      │
│  Outgoing (1)                        │
│  ┌─────────────────────────────────┐ │
│  │ → Meowth  (pending)   [Cancel]  │ │
│  └─────────────────────────────────┘ │
└──────────────────────────────────────┘
```

**Behaviour:**

- **Search bar:** Detects whether the input contains `@` to choose the identifier type. Calls `POST /friends` with either `{ "username": "<value>" }` or `{ "email": "<value>" }` on tap of **Add**. Shows inline success ("Friend request sent!") or error ("User not found", "Already friends"). Never display the looked-up email address in the UI — show only the username once the request is sent.
- **Friends tab:** Populated from the `friends[]` array in `GET /friends`. Each row shows username and an **Invite** button. Tapping **Invite** navigates straight to the game lobby (creates the invite via `POST /game-invites` with that friend's `user_id`).
- **Requests tab:** Badge shows the count of incoming requests. Populated from `incoming[]` (received requests) and `outgoing[]` (sent, awaiting response) from `GET /friends`.
  - **Accept** → `PUT /friends/{friendship_id}` with `{ "action": "accept" }` → moves the row to Friends tab.
  - **Decline** / **Cancel** → `PUT /friends/{friendship_id}` with `{ "action": "reject" }` → removes the row.
- Presence indicators (🟢 online / ⚪ offline) are **decorative placeholders in v1** — the backend has no presence API yet. Show 🟢 for all friends or omit entirely until presence is implemented.
- Empty state (no friends yet): full-page illustration with copy "Add a friend to play with!" and the search bar as the primary action.
- On mount and after each action: re-fetch `GET /friends` to keep the list fresh.

---

### 4. My Pokemon (Roster)

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

### 5. Difficulty Selection (PvB only)

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

Each difficulty corresponds to a **separate bot row** in the `bots` table. The `bots.params` JSONB for each row sets the `time_budget` used by the MCTS engine. The frontend selects the appropriate `bot_id` for the chosen difficulty and sends it in `POST /games`:

```json
{ "bot_id": "<uuid-for-this-difficulty>", "player_side": "red" }
```

| Difficulty | Time budget | Flavour text | DB row name |
|---|---|---|---|
| Easy | 0.5s | Metallic is sleepy | `Metallic (Easy)` |
| Medium | 1.5s | Metallic woke up | `Metallic (Medium)` |
| Hard | 3.0s | Metallic means it | `Metallic (Hard)` |
| Expert | 5.0s | Metallic is scary | `Metallic (Expert)` |
| Master | 10.0s | Good luck... | `Metallic (Master)` |

On app startup the client calls **`GET /bots`** to retrieve `bot_id`, `label`, `flavor`, and `time_budget` for each row (the Next.js **`/play`** page does this). Tapping a difficulty immediately creates the game (no extra confirm step). Metallic is the seeded PvB personality — copy may reference Team Alpha’s AI.

---

### 6. Game Lobby / Waiting Screen

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
│   [Cancel invite]                    │
│                                      │
└──────────────────────────────────────┘
```

**Invite flow:** To invite a friend, the inviter picks from their friends list (fetched via `GET /friends`) and calls `POST /game-invites` with `{ "invitee_id": "<friend's user_id UUID>" }`. There is no join-by-code mechanic — invites are push-only. The invitee sees the pending invite on their next `GET /game-invites` poll and accepts via `PUT /game-invites/{invite_id}` with `{ "action": "accept" }`. The inviter's lobby screen polls `GET /game-invites` (every 2–3s) to detect acceptance and navigate to the game.

---

### 7. Gameplay Screen

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
- **Board orientation:** The API uses 0-indexed rows where **row 0 is Red's back rank** and **row 7 is Blue's back rank**. Always render the board so the **local player's pieces are at the bottom** — flip row order for the Blue player so row 7 appears at the bottom of the screen.
- **Highlights on click** — derived from the `action_type` field of each `LegalMoveOut`:

| `action_type` | Highlight | Color |
|---|---|---|
| `MOVE` | Yellow overlay + center dot | `hl-move` `#F5E028` |
| `ATTACK` | Orange overlay + crosshair dot | `hl-attack` `#F55A19` |
| `QUICK_ATTACK` | Orange overlay + crosshair dot (same as ATTACK; two-step flow below) | `hl-attack` `#F55A19` |
| `POKEBALL_ATTACK` | Orange overlay + Pokéball icon | `hl-attack` `#F55A19` |
| `MASTERBALL_ATTACK` | Deep purple overlay + Masterball icon | `#6B21A8` |
| `FORESIGHT` | Cyan glow overlay | `hl-foresight` `#32D7FA` |
| `TRADE` | Purple overlay | `hl-trade` `#A855F7` |
| `EVOLVE` | Gold pulsing ring on the piece itself | `accent-gold` `#FFD700` |
| `RELEASE` | Green overlay on target square | `#4CAF50` |

  Selected piece: always shows bright blue pulsing ring (`hl-select` `#64A0FF`) regardless of action type.

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
- Contains: "Team Red" / "Team Blue" label, King's HP bar (wide, prominent), active turn indicator, **[Resign]** button (small, destructive-styled, always visible for the local player's banner)
- **`whose_turn` field** in `GameDetail` uses lowercase `"red"` / `"blue"`. Compare against the local player's side to determine turn ownership.
- **Metallic's turn state (PvB):** replace "Your Turn!" with a spinning Pokeball + "Metallic is thinking…" text; board squares subtly dim (50% opacity overlay) so the player knows not to tap. The wait can be up to 10s at Master difficulty — the animation must feel alive, not frozen.
- Tapping **[Resign]** calls `POST /games/{game_id}/resign` and navigates to the Game Over screen with the opponent as winner.

#### Right Sidebar — Contextual Info

- **Selected Piece card** (appears on click): larger sprite, name, index (#1/#2), type badge, HP bar, held item. Disappears when nothing is selected.
- **Move Legend**: always visible, five color swatches with one-word labels. Serves as a permanent reminder for new players.
- **Last Move log**: single line, human-readable string of the most recent move event. Uses type color in the text ("Super Effective!" in orange, "Not Very Effective" in gray). Not a scrollable history — just the last event.

#### Special Move Disambiguation (Mew, Pikachu, and Eevee Evolution)

When the API returns multiple moves sharing the same `(piece_row, piece_col, target_row, target_col)` tuple — i.e. same piece and same destination but different `move_slot` or `action_type` values — a **bottom-sheet picker** slides up ~200px from the bottom of the board. It never covers the full board.

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

Foresight is listed here as one of Mew's attack options (or Espeon's). In the legal moves list it appears as a separate `action_type: "FORESIGHT"` move; the picker merges it with the `ATTACK` options since they share the same target square. Its cyan color distinguishes it in the picker. Selecting it works like any other attack — the cyan highlight on the board shows the pending target.

**Pikachu evolution picker** (one option only — triggers EVOLVE action):
```
┌─────────────────────────────────────────────┐
│  Pikachu wants to evolve!                   │
│                                             │
│  [Raichu⚡]  (costs your turn)              │
│                                             │
│  [Cancel]                                   │
└─────────────────────────────────────────────┘
```

Pikachu's `EVOLVE` move has no `move_slot` disambiguation — there is only one option (Raichu). Show this picker only when the player explicitly taps the gold evolution ring on Pikachu's cell. Cancelling returns to normal piece selection. The `EVOLVE` move payload has the piece's square as both source and target.

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
3. Player clicks a movement destination → move submits with `action_type: "QUICK_ATTACK"`, `target_row/col` = attack square, `secondary_row/col` = landing square
4. A small "Step 1 of 2 — now pick where to move" hint appears in the right sidebar during step 2 so the player is never confused about what to do next

---

### 8. Game Over Screen

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

## API Integration Reference

Key conventions for frontend ↔ backend communication:

| Topic | Rule |
|---|---|
| **Auth** | Access token in `Authorization: Bearer <token>` header. Refresh token in httpOnly cookie; call `POST /auth/refresh` to rotate. |
| **Profile / roster** | `GET /users/me` — user + `pieces` (not `GET /me`). |
| **PvB bot list** | `GET /bots` — public; `bot_id` for `POST /games`. |
| **`whose_turn`** | Lowercase `"red"` \| `"blue"` in `GameDetail`. Compare to local player's side string to determine turn. |
| **`active_player` in state** | Uppercase `"RED"` \| `"BLUE"` — same value, different casing. These two fields are in sync but formatted differently. |
| **Move submission `action_type`** | Send uppercase engine enum names: `"MOVE"`, `"ATTACK"`, `"QUICK_ATTACK"`, `"POKEBALL_ATTACK"`, `"MASTERBALL_ATTACK"`, `"FORESIGHT"`, `"TRADE"`, `"EVOLVE"`, `"RELEASE"`. |
| **History `action_type`** | Move history entries use lowercase: `"move"`, `"attack"`, `"quick_attack"`, `"pokeball_attack"`, `"masterball_attack"`, `"foresight"`, `"foresight_resolve"`, `"evolve"`, `"trade"`, `"release"`. |
| **Piece IDs** | Named pieces (rooks, knights, bishops, queen, kings) carry a UUID string `id`. Pawns (Pokéballs, Safetyballs) always have `id: null`. Match pieces to roster entries by UUID. |
| **Board coordinates** | 0-indexed, integers. Row 0 = Red's back rank. Flip rendering for Blue player so their back rank is at the bottom of the screen. |
| **Legal moves request** | `GET /games/{id}/legal_moves?piece_row=R&piece_col=C` — pass integers. Returns `list[LegalMoveOut]`. |
| **Move submission** | Submit one object from the legal moves list verbatim to `POST /games/{id}/move`. Do not modify field values. |
| **Disambiguation trigger** | Show the bottom-sheet picker when multiple legal moves share the same `(piece_row, piece_col, target_row, target_col)` but differ in `move_slot` or `action_type`. |
| **Active vs completed games** | `GET /games` returns `active` (no cap) and `completed` (capped at 10 most recently updated). |
| **Game state board** | `state.board` contains only on-board pieces. Captured pieces are removed from the array — do not attempt to render them. |
| **Foresight `resolves_on_turn`** | Absolute turn number stored in `pending_foresight[team].resolves_on_turn`. The persistent cyan glow should remain until that turn resolves. |
| **XP source** | Read `xp_earned` and `xp_applied` from `game_pokemon_map` entries (returned via the completed `GameDetail` or a future `/games/{id}/xp` endpoint). Do not recompute on the client. |
| **Error format** | All errors: `{ "error": "<code>", "detail": "<message>" }`. Key codes: `not_your_turn` (409), `illegal_move` (400), `game_not_active` (409), `engine_error` (503). |

---

## UX Principles Applied

| Problem | Solution |
|---|---|
| Kids don't know chess notation | No algebraic notation anywhere — everything is visual highlight on the board |
| Too many possible actions | Right sidebar is fully contextual — only appears on click, shows only relevant info |
| Bot latency (up to 10s at Master) | Explicit "Bot thinking…" spinner + board grayout — no ambiguity about whose turn it is |
| Stochastic Pokeball outcome | Brief ball-wiggle animation before result reveal — makes randomness feel exciting |
| Mew / Pikachu / Eevee multi-option moves | Bottom-sheet picker — preserves board context, minimal taps |
| Foresight is invisible between turns | Persistent cyan glow + eye badge on target square while pending |
| HP is critical but clutters the board | Thin HP arc on the piece ring (always visible) + full bar in sidebar on selection |
| Stored Pokemon inside a Safetyball | Small sprite badge on the ball's cell + stacked card in sidebar on hover |
| Roster has more than 5 Pokemon | Scrollable card list, indexed by species number (#1, #2) |
| Captured pieces state not in API | Captured pieces panel removed — not shown anywhere |
| Evolution is a special moment | Flashy bottom-sheet picker for in-game evolution; post-game cutscene for XP-triggered evolution |
| Player wants to quit mid-game | Resign button in local player's banner; calls `POST /games/{id}/resign` |

---

## Resolved Decisions

| # | Question | Decision |
|---|---|---|
| Q1 | Mew / Eevee multi-option move UI | Bottom-sheet picker. Mew: up to 4 options (3 attacks + Foresight). Eevee: 5 evolution sprites. Pikachu: 1 option (Raichu), simple confirm sheet. |
| Q2 | PvP scope | **PvP is in scope for v1.** Play vs Friend is a hard requirement. Friends + invite endpoints ship in v1. |
| Q3 | Move response contract | Single GameDetail payload. "Metallic is thinking…" state (spinning Pokeball, dimmed board) covers wait time. |
| Q4 | Legal moves in GameDetail | **Kept separate.** `GET /games/{id}/legal_moves` remains its own endpoint. GameDetail never embeds legal moves. |
| Q5 | XP formula | XP = damage dealt by that piece this game. Display reads values from API — formula lives server-side only. |
| Q6 | King/Queen evolution persistence | **Kings and Queen never persistently evolve.** Pikachu/Eevee always start fresh each game (in-game evolution only); Mew has no evolution. XP is tracked for all three but no evolution progress bar is shown. Only rooks, knights, and bishops evolve post-game. |
| Q7 | Difficulty → API mapping | Each difficulty level corresponds to a separate bot row in the `bots` table. `POST /games` receives a `bot_id` UUID. No `time_budget` or `difficulty` field in the game creation request — time budget is baked into the bot row's `params` JSONB. |
| Q8 | PvP invite flow | No join-by-code. Inviter picks from friends list (uses `user_id` UUID as `invitee_id`). Invitee sees invite on `GET /game-invites` poll and accepts via `PUT /game-invites/{id}`. |
| Orientation | Primary target | Tablet and phone. Portrait is primary; landscape is secondary. Board fills width in portrait; collapsible bottom drawer for contextual info. |
| Difficulty | Selector levels | Easy (0.5s) / Medium (1.5s) / Hard (3s) / Expert (5s) / Master (10s). Selected before game creation. Flavour text per tier. |
| Sound | v1 scope | Simple sound effects in v1 (piece tap, move placement, attack hit, Pokeball shake, evolution sting, win/loss). Audio architecture must be extensible (volume controls, mute, easy asset swap) without blocking v1 delivery. Sound is a future-enhancement surface — do not let audio scope creep delay the core gameplay build. |

### Sound Architecture Note

Build with a thin audio manager abstraction from the start (e.g. a single `SoundManager` module with named slots: `play('piece_move')`, `play('attack_hit')`, etc.). v1 populates each slot with a simple sound file. Future versions can swap in richer effects, music, or voice without changing call sites. Keep the asset pipeline simple — a flat directory of `.mp3` / `.ogg` files, no complex audio graph needed for v1.
