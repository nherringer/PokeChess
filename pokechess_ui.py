#!/usr/bin/env python3
"""
PokeChess — Play against the MCTS bot.

Usage:
    python pokechess_ui.py
    python pokechess_ui.py --budget 2.0
"""
from __future__ import annotations
import os, sys, threading, random, time, argparse
from typing import Optional, List, Tuple, Dict

import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.state import GameState, Team, PieceType, Item, PIECE_STATS, PAWN_TYPES, KING_TYPES
from engine.moves import get_legal_moves, Move, ActionType
from engine.rules import apply_move, is_terminal, hp_winner
from bot.mcts import MCTS
from bot.transposition import TranspositionTable

# ──────────────────────────────────────────────────────────────────────────────
# Layout
# ──────────────────────────────────────────────────────────────────────────────
TT_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transposition_table.bin')

WIN_W, WIN_H = 1140, 780
BOARD_X, BOARD_Y = 20, 70
CELL = 78
RING_R      = 36   # outer ring radius (fits inside CELL=78 given the 4px cy offset)
RING_BORDER = 6    # team-colour ring thickness in pixels
SPRITE_PX   = (RING_R - RING_BORDER) * 2  # sprite fills the inner circle
PANEL_X = BOARD_X + 8 * CELL + 20   # 664
PANEL_W = WIN_W - PANEL_X - 30      # leaves ~30px right margin to avoid edge clipping

# Captured-pieces chip geometry (drawn below board)
CHIP_R        = 12
CHIP_INNER_R  = CHIP_R - 2
CHIP_SPRITE_PX = CHIP_INNER_R * 2

# ──────────────────────────────────────────────────────────────────────────────
# Palette
# ──────────────────────────────────────────────────────────────────────────────
BG         = (18, 20, 30)
LIGHT_SQ   = (235, 235, 208)
DARK_SQ    = (110, 143, 82)
HL_SELECT  = (100, 160, 255)
HL_MOVE    = (245, 225, 40)
HL_ATTACK  = (245, 90,  25)
HL_FORE    = (50,  215, 250)
HL_ALPHA   = 145

C_WHITE    = (232, 232, 232)
C_DIM      = (140, 140, 150)
C_RED      = (215, 55,  55)
C_BLUE     = (60,  115, 225)
C_GREEN    = (65,  195, 80)
C_YELLOW   = (238, 200, 48)
C_ORANGE   = (238, 140, 28)
C_CYAN     = (50,  215, 235)
C_PANEL    = (25,  27,  38)
C_CARD     = (35,  38,  52)
C_DIVIDER  = (48,  52,  68)
C_BTN      = (45,  48,  64)
C_BTN_HOV  = (60,  64,  82)
C_BTN_ACT  = (72, 102, 192)
C_BTN_WARN = (175, 55, 50)
C_BTN_WH   = (215, 75, 65)

SPRITE_DIR = os.path.join(os.path.dirname(__file__), 'demo', 'sprites')

SPRITE_FILES = {
    PieceType.BULBASAUR:  '1.png',
    PieceType.CHARMANDER: '4.png',
    PieceType.SQUIRTLE:   '7.png',
    PieceType.PIKACHU:    '25.png',
    PieceType.RAICHU:     '26.png',
    PieceType.EEVEE:      '133.png',
    PieceType.VAPOREON:   '134.png',
    PieceType.JOLTEON:    '135.png',
    PieceType.FLAREON:    '136.png',
    PieceType.MEW:        '151.png',
    PieceType.ESPEON:     '196.png',
    PieceType.LEAFEON:    '470.png',
}

PIECE_LABEL = {
    PieceType.BULBASAUR:  'Bulbasaur',
    PieceType.CHARMANDER: 'Charmander',
    PieceType.SQUIRTLE:   'Squirtle',
    PieceType.PIKACHU:    'Pikachu',
    PieceType.RAICHU:     'Raichu',
    PieceType.EEVEE:      'Eevee',
    PieceType.VAPOREON:   'Vaporeon',
    PieceType.JOLTEON:    'Jolteon',
    PieceType.FLAREON:    'Flareon',
    PieceType.MEW:        'Mew',
    PieceType.ESPEON:     'Espeon',
    PieceType.LEAFEON:    'Leafeon',
    PieceType.POKEBALL:          'Stealball',
    PieceType.MASTERBALL:        'Master Stealball',
    PieceType.SAFETYBALL:        'Safetyball',
    PieceType.MASTER_SAFETYBALL: 'Master Safetyball',
}

ACTION_LABEL = {
    ActionType.MOVE:         'Move',
    ActionType.ATTACK:       'Attack',
    ActionType.FORESIGHT:    'Foresight',
    ActionType.TRADE:        'Trade',
    ActionType.EVOLVE:       'Evolve',
    ActionType.QUICK_ATTACK: 'Quick Attack',
    ActionType.RELEASE:      'Release',
}

MEW_SLOTS  = {0: 'Fire Blast', 1: 'Hydro Pump', 2: 'Solar Beam'}
EVO_SLOTS  = {0: 'Vaporeon', 1: 'Flareon', 2: 'Leafeon', 3: 'Jolteon', 4: 'Espeon'}


# ──────────────────────────────────────────────────────────────────────────────
# Gated transposition table (controls bot's access to prior-game knowledge)
# ──────────────────────────────────────────────────────────────────────────────
class GatedTT(TranspositionTable):
    """Wraps TranspositionTable; probabilistically gates reads by access_pct."""
    def __init__(self):
        super().__init__()
        self.access_pct = 1.0   # 0.0 – 1.0

    def get(self, h: int):
        if self.access_pct >= 1.0 or random.random() < self.access_pct:
            return super().get(h)
        return (0.0, 0)


# ──────────────────────────────────────────────────────────────────────────────
# Simple UI widgets
# ──────────────────────────────────────────────────────────────────────────────
class Button:
    def __init__(self, x, y, w, h, label, color=None, text_color=None,
                 font=None, hover_color=None, corner_radius=6):
        self.rect   = pygame.Rect(x, y, w, h)
        self.label  = label
        self.color  = color or C_BTN
        self.hcolor = hover_color or C_BTN_HOV
        self.tcolor = text_color or C_WHITE
        self.font   = font
        self.radius = corner_radius
        self.active = False     # visually pressed/selected

    def draw(self, surf, mouse_pos):
        hovered = self.rect.collidepoint(mouse_pos)
        if self.active:
            c = C_BTN_ACT
        elif hovered:
            c = self.hcolor
        else:
            c = self.color
        pygame.draw.rect(surf, c, self.rect, border_radius=self.radius)
        pygame.draw.rect(surf, C_DIVIDER, self.rect, 1, border_radius=self.radius)
        if self.font:
            txt = self.font.render(self.label, True, self.tcolor)
            surf.blit(txt, txt.get_rect(center=self.rect.center))

    def hit(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos))


class Slider:
    """Horizontal slider.  value is always in [min_val, max_val]."""
    def __init__(self, x, y, w, min_val, max_val, init_val,
                 label='', fmt='{:.1f}', font=None, lbl_font=None):
        self.x, self.y, self.w = x, y, w
        self.min_v, self.max_v = min_val, max_val
        self.value   = init_val
        self.label   = label
        self.fmt     = fmt
        self.font    = font
        self.lbl_font = lbl_font
        self._drag   = False
        self.track_h = 6
        self.knob_r  = 9

    @property
    def _track_y(self):
        return self.y + (30 if self.label else 0)

    def _val_to_x(self, v):
        t = (v - self.min_v) / (self.max_v - self.min_v)
        return int(self.x + t * self.w)

    def _x_to_val(self, px):
        t = (px - self.x) / self.w
        t = max(0.0, min(1.0, t))
        return self.min_v + t * (self.max_v - self.min_v)

    def draw(self, surf):
        ty = self._track_y
        if self.label and self.lbl_font:
            lbl = self.lbl_font.render(self.label, True, C_DIM)
            surf.blit(lbl, (self.x, self.y))
            val_txt = self.font.render(self.fmt.format(self.value), True, C_WHITE)
            surf.blit(val_txt, (self.x + self.w - val_txt.get_width(), self.y))
        # track
        pygame.draw.rect(surf, C_DIVIDER,
                         (self.x, ty - self.track_h//2, self.w, self.track_h),
                         border_radius=3)
        kx = self._val_to_x(self.value)
        fill_w = kx - self.x
        if fill_w > 0:
            pygame.draw.rect(surf, C_BTN_ACT,
                             (self.x, ty - self.track_h//2, fill_w, self.track_h),
                             border_radius=3)
        pygame.draw.circle(surf, C_WHITE, (kx, ty), self.knob_r)
        pygame.draw.circle(surf, C_BTN_ACT, (kx, ty), self.knob_r - 2)

    def handle(self, event):
        ty = self._track_y
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            kx = self._val_to_x(self.value)
            if abs(event.pos[0] - kx) < 14 and abs(event.pos[1] - ty) < 14:
                self._drag = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag = False
        elif event.type == pygame.MOUSEMOTION and self._drag:
            self.value = self._x_to_val(event.pos[0])
        return self._drag


class ScrollLog:
    """Scrollable text log panel."""
    def __init__(self, x, y, w, h, font, max_lines=200):
        self.rect     = pygame.Rect(x, y, w, h)
        self.font     = font
        self.lines: List[Tuple[str, tuple]] = []
        self.max_lines = max_lines
        self.scroll   = 0   # lines scrolled from bottom
        self._surf    = None

    def add(self, text: str, color=None):
        self.lines.append((text, color or C_DIM))
        if len(self.lines) > self.max_lines:
            self.lines.pop(0)
        self.scroll = 0   # snap to bottom

    def draw(self, surf, mouse_pos):
        pygame.draw.rect(surf, C_CARD, self.rect, border_radius=4)
        pygame.draw.rect(surf, C_DIVIDER, self.rect, 1, border_radius=4)
        lh   = self.font.get_height() + 2
        rows = self.rect.h // lh
        start = max(0, len(self.lines) - rows - self.scroll)
        end   = min(len(self.lines), start + rows)
        clip  = surf.get_clip()
        surf.set_clip(self.rect.inflate(-4, -4))
        for i, idx in enumerate(range(start, end)):
            txt, col = self.lines[idx]
            rendered = self.font.render(txt, True, col)
            y = self.rect.y + 4 + i * lh
            surf.blit(rendered, (self.rect.x + 6, y))
        surf.set_clip(clip)

    def handle_scroll(self, event):
        if self.rect.collidepoint(pygame.mouse.get_pos()):
            if event.type == pygame.MOUSEWHEEL:
                lh = self.font.get_height() + 2
                rows = self.rect.h // lh
                self.scroll = max(0, min(len(self.lines) - rows,
                                         self.scroll + event.y))


# ──────────────────────────────────────────────────────────────────────────────
# Main application
# ──────────────────────────────────────────────────────────────────────────────
class PokeChessApp:
    # ── init ────────────────────────────────────────────────────────────────
    def __init__(self, init_budget: float = 1.0):
        os.environ.setdefault('SDL_VIDEO_WINDOW_POS', '0,0')
        pygame.init()
        pygame.display.set_caption('PokeChess')
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        self.clock  = pygame.time.Clock()

        # fonts
        self.f_title  = pygame.font.SysFont('Arial', 22, bold=True)
        self.f_head   = pygame.font.SysFont('Arial', 15, bold=True)
        self.f_body   = pygame.font.SysFont('Arial', 13)
        self.f_small  = pygame.font.SysFont('Arial', 11)
        self.f_coord  = pygame.font.SysFont('Arial', 10)
        self.f_log    = pygame.font.SysFont('Courier New', 12)

        # sprites
        self._sprites: Dict[PieceType, pygame.Surface] = {}
        self._load_sprites()

        # persistent transposition table (loaded from disk if available)
        self.shared_tt = GatedTT()
        self.shared_tt.load(TT_SAVE_PATH)

        # captured pieces: team → list of PieceType lost by that team this game
        self._captures: dict[Team, list] = {Team.RED: [], Team.BLUE: []}

        # game state
        self.state: Optional[GameState]   = None
        self.history: List[GameState]     = []   # board states (snaps after each move)
        self.move_log: List[str]          = []   # textual move descriptions
        self.hist_idx: int                = -1   # -1 = live game
        self.selected: Optional[Tuple[int,int]] = None
        self.legal_for_sel: List[Move]    = []
        self.pending_moves: List[Move]    = []   # disambiguation candidates
        self.player_color: Team           = Team.RED

        # bot state
        self._bot_thread: Optional[threading.Thread] = None
        self._bot_result: Optional[Move]  = None
        self._bot_lock   = threading.Lock()
        self._bot_running = False

        # UI state
        self.status_msg   = ''
        self.status_color = C_WHITE
        self.tooltip_text = ''
        self.bot_move_highlight: Optional[Tuple[int,int,int,int]] = None   # (fr,fc,tr,tc)
        self._last_bot_move_time = 0.0

        # ── build UI widgets ─────────────────────────────────────────────────
        px = PANEL_X

        # color toggle
        self.btn_red  = Button(px, 90,  100, 32, 'Play as RED',
                               font=self.f_body, corner_radius=6)
        self.btn_blue = Button(px+108, 90, 104, 32, 'Play as BLUE',
                               font=self.f_body, corner_radius=6)
        self.btn_red.active = True

        # bot sliders
        sx = px
        sw = PANEL_W - 4   # PANEL_W already includes 30px right margin via the constant
        self.sl_budget = Slider(sx, 160, sw, 0.2, 10.0, init_budget,
                                label='Bot time budget (s)',
                                fmt='{:.1f}s',
                                font=self.f_body, lbl_font=self.f_small)
        self.sl_tt     = Slider(sx, 215, sw, 0.0, 1.0, 1.0,
                                label='TT access  (prior knowledge)',
                                fmt='{:.0%}',
                                font=self.f_body, lbl_font=self.f_small)

        # game controls
        bw = (PANEL_W - 10) // 2 - 2
        self.btn_new   = Button(px,       278, bw, 34, 'New Game',
                                font=self.f_body, corner_radius=6)
        self.btn_undo  = Button(px+bw+4,  278, bw, 34, 'Undo',
                                font=self.f_body, corner_radius=6)

        # history nav
        nw = (PANEL_W - 10) // 4 - 2
        self.btn_hprev = Button(px,          320, nw,   28, '|< Start',
                                font=self.f_small, corner_radius=5)
        self.btn_prev  = Button(px+nw+3,     320, nw,   28, '< Prev',
                                font=self.f_small, corner_radius=5)
        self.btn_hnext = Button(px+2*(nw+3), 320, nw,   28, 'Next >',
                                font=self.f_small, corner_radius=5)
        self.btn_live  = Button(px+3*(nw+3), 320, nw,   28, 'Live >|',
                                font=self.f_small, corner_radius=5)

        # move log
        self.log_widget = ScrollLog(px, 338, PANEL_W - 10, WIN_H - 338 - 10,
                                    font=self.f_log)

        # action buttons (disambiguation) — built dynamically, placed below board
        self.action_btns: List[Button] = []

        self.new_game()

    # ── sprite loading ───────────────────────────────────────────────────────
    def _load_sprites(self):
        self._chip_sprites: Dict[PieceType, pygame.Surface] = {}
        for pt, fname in SPRITE_FILES.items():
            path = os.path.join(SPRITE_DIR, fname)
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                # Crop transparent padding so the Pokemon fills the circle
                bb = img.get_bounding_rect()
                if bb.width > 0 and bb.height > 0:
                    cropped = pygame.Surface((bb.width, bb.height), pygame.SRCALPHA)
                    cropped.blit(img, (0, 0), bb)
                    img = cropped
                self._sprites[pt] = pygame.transform.smoothscale(img, (SPRITE_PX, SPRITE_PX))
                self._chip_sprites[pt] = pygame.transform.smoothscale(
                    img, (CHIP_SPRITE_PX, CHIP_SPRITE_PX))

    # ── coordinate helpers ───────────────────────────────────────────────────
    def _board_to_screen(self, row: int, col: int) -> Tuple[int, int]:
        """Top-left pixel of the cell for (row, col)."""
        if self.player_color == Team.RED:
            sr = 7 - row   # row 0 → bottom
            sc = col
        else:
            sr = row
            sc = 7 - col
        return (BOARD_X + sc * CELL, BOARD_Y + sr * CELL)

    def _screen_to_board(self, px: int, py: int) -> Optional[Tuple[int, int]]:
        bx, by = px - BOARD_X, py - BOARD_Y
        if not (0 <= bx < 8 * CELL and 0 <= by < 8 * CELL):
            return None
        sc, sr = bx // CELL, by // CELL
        if self.player_color == Team.RED:
            return (7 - sr, sc)
        else:
            return (sr, 7 - sc)

    # ── game logic ───────────────────────────────────────────────────────────
    def new_game(self):
        """Start a fresh game (keeps the shared TT)."""
        # Abandon any in-flight bot thread (it's a daemon and will terminate on its own).
        # We clear the flags first so its result is ignored when it eventually finishes.
        with self._bot_lock:
            self._bot_running = False
            self._bot_result  = None
        self.state    = GameState.new_game()
        self.history  = [self.state]
        self.move_log = []
        self.hist_idx = -1
        self.selected = None
        self.legal_for_sel = []
        self.pending_moves = []
        self.action_btns   = []
        self.bot_move_highlight = None
        self._captures = {Team.RED: [], Team.BLUE: []}
        self.log_widget.lines.clear()
        self.log_widget.add('─── New game ───', C_YELLOW)
        self.log_widget.add(f'You play as {"RED" if self.player_color == Team.RED else "BLUE"}', C_WHITE)
        self.log_widget.add(f'Bot budget: {self.sl_budget.value:.1f}s', C_DIM)
        tt_pct = int(self.sl_tt.value * 100)
        self.log_widget.add(f'TT access: {tt_pct}%   |   entries: {len(self.shared_tt):,}', C_DIM)
        self._update_status()
        if self._is_bot_turn():
            self._start_bot()

    def undo(self):
        """Undo back to the previous human-turn state."""
        if len(self.history) <= 1:
            return
        # If the bot is thinking, abandon its result but still undo
        self._bot_running = False
        self._bot_result  = None
        # Pop states until it's the human's turn (or we've popped enough)
        popped = 0
        while len(self.history) > 1 and popped < 4:
            self.history.pop()
            popped += 1
            if self.history[-1].active_player == self.player_color:
                break
        self.hist_idx = -1
        self.selected = None
        self.legal_for_sel = []
        self.pending_moves = []
        self.action_btns   = []
        self.bot_move_highlight = None
        self.log_widget.add('Undo', C_ORANGE)
        self._update_status()

    # ── HP and capture helpers ────────────────────────────────────────────────

    _PAWN_HP = {
        PieceType.POKEBALL:          50,
        PieceType.MASTERBALL:        200,
        PieceType.SAFETYBALL:        50,
        PieceType.MASTER_SAFETYBALL: 200,
    }

    def _team_hp(self, state: GameState, team: Team) -> int:
        total = 0
        for p in state.all_pieces(team):
            total += self._PAWN_HP.get(p.piece_type, p.current_hp)
            if p.stored_piece is not None:
                total += p.stored_piece.current_hp
        return total

    def _record_captures(self, old_state: GameState, new_state: GameState) -> None:
        """Detect pieces that disappeared between states and record them as captured."""
        def counts(state):
            c: dict[tuple, int] = {}
            for p in state.all_pieces():
                c[(p.team, p.piece_type)] = c.get((p.team, p.piece_type), 0) + 1
                if p.stored_piece is not None:
                    k = (p.stored_piece.team, p.stored_piece.piece_type)
                    c[k] = c.get(k, 0) + 1
            return c

        old_c = counts(old_state)
        new_c = counts(new_state)

        for (team, ptype), old_n in old_c.items():
            removed = old_n - new_c.get((team, ptype), 0)
            if removed <= 0:
                continue
            # Skip king evolutions: king disappeared but team's king count unchanged
            if ptype in KING_TYPES:
                old_kings = sum(v for (t, pt), v in old_c.items() if t == team and pt in KING_TYPES)
                new_kings = sum(v for (t, pt), v in new_c.items() if t == team and pt in KING_TYPES)
                if new_kings >= old_kings:
                    continue
            for _ in range(removed):
                self._captures[team].append(ptype)

    def _live_state(self) -> GameState:
        return self.history[-1]

    def _viewing_state(self) -> GameState:
        if self.hist_idx == -1:
            return self._live_state()
        return self.history[self.hist_idx]

    def _is_bot_turn(self) -> bool:
        s = self._live_state()
        done, _ = is_terminal(s)
        return (not done) and (s.active_player != self.player_color)

    def _is_human_turn(self) -> bool:
        s = self._live_state()
        done, _ = is_terminal(s)
        return (not done) and (s.active_player == self.player_color)

    def _update_status(self):
        s  = self._live_state()
        done, winner = is_terminal(s)
        if done:
            if winner == self.player_color:
                self.status_msg   = 'You win!'
                self.status_color = C_GREEN
            elif winner is None:
                self.status_msg   = 'Draw'
                self.status_color = C_YELLOW
            else:
                self.status_msg   = 'Bot wins!'
                self.status_color = C_RED
        elif self._bot_running:
            self.status_msg   = f'Bot thinking...  (budget {self.sl_budget.value:.1f}s)'
            self.status_color = C_CYAN
        elif self.hist_idx != -1:
            n = len(self.history)
            self.status_msg   = f'History view  [{self.hist_idx + 1}/{n}]'
            self.status_color = C_YELLOW
        elif s.active_player == self.player_color:
            color_name = 'RED' if s.active_player == Team.RED else 'BLUE'
            self.status_msg   = f'Your turn ({color_name})  —  turn {s.turn_number}'
            self.status_color = C_WHITE
        else:
            color_name = 'RED' if s.active_player == Team.RED else 'BLUE'
            self.status_msg   = f'Waiting for bot ({color_name})'
            self.status_color = C_DIM

    # ── bot thread ───────────────────────────────────────────────────────────
    def _start_bot(self):
        if self._bot_running:
            return
        self._bot_running = True
        self._bot_result  = None
        self.shared_tt.access_pct = self.sl_tt.value
        budget = max(0.1, self.sl_budget.value)
        state  = self._live_state()

        def _think(s, b, tt):
            move = None
            try:
                bot  = MCTS(time_budget=b, transposition=tt)
                move = bot.select_move(s)
            except Exception:
                import traceback
                traceback.print_exc()
                self.log_widget.add('Bot error — see terminal', C_ORANGE)
            with self._bot_lock:
                self._bot_result  = move
                self._bot_running = False

        t = threading.Thread(target=_think,
                             args=(state, budget, self.shared_tt),
                             daemon=True)
        t.start()
        self._update_status()

    def _maybe_apply_bot_move(self):
        with self._bot_lock:
            if self._bot_result is None:
                return
            move = self._bot_result
            self._bot_result = None

        s = self._live_state()
        done, _ = is_terminal(s)
        if done:
            return

        outcomes = apply_move(s, move)
        is_stochastic = len(outcomes) > 1
        if is_stochastic:
            picked = random.choices(range(len(outcomes)),
                                    weights=[p for _, p in outcomes])[0]
        else:
            picked = 0
        new_state = outcomes[picked][0]

        pr, pc = move.piece_row, move.piece_col
        tr, tc = move.target_row, move.target_col
        piece  = s.board[pr][pc]
        target = s.board[tr][tc]
        p_name = PIECE_LABEL.get(piece.piece_type, '?') if piece else '?'
        t_name = PIECE_LABEL.get(target.piece_type, '?') if target else '?'
        team_col = C_RED if s.active_player == Team.RED else C_BLUE
        slot_note = ''
        if move.action_type == ActionType.ATTACK and piece and piece.piece_type == PieceType.MEW:
            slot_note = f' [{MEW_SLOTS.get(move.move_slot, "?")}]'
        if move.action_type == ActionType.EVOLVE:
            slot_note = f' -> {EVO_SLOTS.get(move.move_slot, "?")}'
        if move.action_type == ActionType.TRADE:
            self.log_widget.add(
                f'Bot  Trade  {p_name} ↔ {t_name}', C_DIM)
        else:
            self.log_widget.add(
                f'Bot  {ACTION_LABEL.get(move.action_type,"?")} '
                f'{p_name}{slot_note} ({pr},{pc})→({tr},{tc})',
                team_col)
            # Stochastic outcome note
            if is_stochastic:
                if picked == 0:
                    self.log_widget.add(f'  >> Caught {t_name}!', C_GREEN)
                else:
                    self.log_widget.add(f'  >> {t_name} got away!', C_ORANGE)
            # Pokemon-attacks-pokeball note (deterministic catch)
            elif (move.action_type == ActionType.ATTACK and target is not None
                  and target.piece_type in PAWN_TYPES):
                self.log_widget.add(f'  >> {p_name} was caught by {t_name}!', C_ORANGE)

        self.bot_move_highlight = (pr, pc, tr, tc)
        self._last_bot_move_time = time.monotonic()

        self._record_captures(s, new_state)
        self.history.append(new_state)
        self._update_status()
        if self._is_bot_turn():
            self._start_bot()

    # ── move execution (human) ───────────────────────────────────────────────
    def _execute_move(self, move: Move):
        s = self._live_state()
        outcomes = apply_move(s, move)
        is_stochastic = len(outcomes) > 1
        if is_stochastic:
            picked = random.choices(range(len(outcomes)),
                                    weights=[p for _, p in outcomes])[0]
        else:
            picked = 0
        new_state = outcomes[picked][0]

        pr, pc = move.piece_row, move.piece_col
        tr, tc = move.target_row, move.target_col
        piece  = s.board[pr][pc]
        target = s.board[tr][tc]
        p_name = PIECE_LABEL.get(piece.piece_type, '?') if piece else '?'
        t_name = PIECE_LABEL.get(target.piece_type, '?') if target else '?'
        team_col = C_RED if s.active_player == Team.RED else C_BLUE
        slot_note = ''
        if move.action_type == ActionType.ATTACK and piece and piece.piece_type == PieceType.MEW:
            slot_note = f' [{MEW_SLOTS.get(move.move_slot, "?")}]'
        if move.action_type == ActionType.EVOLVE:
            slot_note = f' -> {EVO_SLOTS.get(move.move_slot, "?")}'
        if move.action_type == ActionType.TRADE:
            self.log_widget.add(
                f'You  Trade  {p_name} ↔ {t_name}', C_DIM)
        else:
            self.log_widget.add(
                f'You  {ACTION_LABEL.get(move.action_type,"?")} '
                f'{p_name}{slot_note} ({pr},{pc})->({tr},{tc})',
                team_col)
            # Stochastic outcome note
            if is_stochastic:
                if picked == 0:
                    self.log_widget.add(f'  >> Caught {t_name}!', C_GREEN)
                else:
                    self.log_widget.add(f'  >> {t_name} got away!', C_ORANGE)
            # Pokemon-attacks-pokeball note (deterministic catch)
            elif (move.action_type == ActionType.ATTACK and target is not None
                  and target.piece_type in PAWN_TYPES):
                self.log_widget.add(f'  >> {p_name} was caught by {t_name}!', C_ORANGE)

        self._record_captures(s, new_state)
        self.history.append(new_state)
        self.selected = None
        self.legal_for_sel = []
        self.pending_moves = []
        self.action_btns   = []
        self._update_status()

        done, winner = is_terminal(new_state)
        if not done and self._is_bot_turn():
            self._start_bot()

    # ── click handling ───────────────────────────────────────────────────────
    def _on_board_click(self, row: int, col: int):
        # History mode: only allow deselect / do nothing
        if self.hist_idx != -1:
            self.hist_idx = -1
            self.action_btns = []
            self._update_status()
            return

        if not self._is_human_turn():
            return

        s = self._live_state()

        # If disambiguation buttons are active, ignore board clicks
        if self.pending_moves:
            return

        piece = s.board[row][col]

        if self.selected is None:
            # Select own piece
            if piece and piece.team == self.player_color:
                self.selected = (row, col)
                all_legal = get_legal_moves(s)
                self.legal_for_sel = [m for m in all_legal
                                      if m.piece_row == row and m.piece_col == col]
                self.action_btns = []
        else:
            sr, sc = self.selected

            if (row, col) == (sr, sc):
                # Clicking the selected piece's own square:
                # check for EVOLVE moves (target == piece square) before deselecting
                evo_moves = [m for m in self.legal_for_sel
                             if m.action_type == ActionType.EVOLVE]
                if evo_moves:
                    self.pending_moves = evo_moves
                    self._build_action_buttons(evo_moves)
                else:
                    # Deselect
                    self.selected = None
                    self.legal_for_sel = []
                    self.pending_moves = []
                    self.action_btns   = []
                return

            if piece and piece.team == self.player_color:
                # Check for TRADE moves from selected piece to this ally first
                trade_moves = [m for m in self.legal_for_sel
                               if m.action_type == ActionType.TRADE
                               and m.target_row == row and m.target_col == col]
                if trade_moves:
                    # Always show confirmation panel (even for a single trade move)
                    self.pending_moves = trade_moves
                    self._build_action_buttons(trade_moves)
                    return
                # Check for MOVE moves targeting this ally (e.g. Safetyball storage)
                move_to_ally = [m for m in self.legal_for_sel
                                if m.action_type == ActionType.MOVE
                                and m.target_row == row and m.target_col == col]
                if move_to_ally:
                    self._execute_move(move_to_ally[0])
                    return
                # No applicable move → switch selection to the clicked ally
                all_legal = get_legal_moves(s)
                self.selected = (row, col)
                self.legal_for_sel = [m for m in all_legal
                                      if m.piece_row == row and m.piece_col == col]
                self.pending_moves = []
                self.action_btns   = []
                return

            # Find moves to the clicked enemy/empty target
            cands = [m for m in self.legal_for_sel
                     if m.target_row == row and m.target_col == col]
            # Also check secondary target for Quick Attack
            if not cands:
                cands = [m for m in self.legal_for_sel
                         if m.action_type == ActionType.QUICK_ATTACK
                         and m.secondary_row == row and m.secondary_col == col]

            if not cands:
                # Click on a non-reachable square → deselect
                self.selected = None
                self.legal_for_sel = []
                self.pending_moves = []
                self.action_btns   = []
                return

            if len(cands) == 1:
                self._execute_move(cands[0])
            else:
                # Disambiguation
                self.pending_moves = cands
                self._build_action_buttons(cands)

    def _build_action_buttons(self, moves: List[Move]):
        self.action_btns = []
        bx = PANEL_X
        bw = PANEL_W - 10
        by = 374   # below history nav (ends at y≈348) with room for header
        bh = 32
        pad = 4

        # Deduplicate: Quick Attack is keyed by (dest, attack-target); others by (type, slot)
        seen = set()
        unique: List[Move] = []
        for m in moves:
            if m.action_type == ActionType.QUICK_ATTACK:
                key = (m.action_type, m.target_row, m.target_col, m.secondary_row, m.secondary_col)
            else:
                key = (m.action_type, m.move_slot)
            if key not in seen:
                seen.add(key)
                unique.append(m)

        s = self._live_state()
        for i, m in enumerate(unique):
            at  = m.action_type
            lbl = ACTION_LABEL.get(at, '?')
            if at == ActionType.ATTACK and s.board[m.piece_row][m.piece_col]:
                p = s.board[m.piece_row][m.piece_col]
                if p.piece_type == PieceType.MEW:
                    lbl = MEW_SLOTS.get(m.move_slot, lbl)
            if at == ActionType.EVOLVE:
                lbl = f'Evolve → {EVO_SLOTS.get(m.move_slot, "?")}'
            if at == ActionType.QUICK_ATTACK:
                target = s.board[m.secondary_row][m.secondary_col]
                t_name = PIECE_LABEL.get(target.piece_type, '?') if target else '?'
                lbl = f'QA via ({m.target_row},{m.target_col}) → {t_name}'
            # Place buttons vertically in panel, below the nav row
            y = by + i * (bh + pad)
            btn = Button(bx, y, bw, bh, lbl,
                         color=C_BTN_ACT, font=self.f_body, corner_radius=6)
            btn.active = False
            btn._move = m
            self.action_btns.append(btn)

        # Cancel button
        y = by + len(unique) * (bh + pad)
        cancel = Button(bx, y, bw, bh, 'Cancel',
                        color=C_BTN_WARN, hover_color=C_BTN_WH,
                        font=self.f_body, corner_radius=6)
        cancel._move = None
        self.action_btns.append(cancel)

    # ── event loop ───────────────────────────────────────────────────────────
    def run(self):
        while True:
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.shared_tt.save(TT_SAVE_PATH)
                    pygame.quit()
                    return

                # Sliders
                self.sl_budget.handle(event)
                self.sl_tt.handle(event)

                # Log scroll
                self.log_widget.handle_scroll(event)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos

                    # Color buttons
                    if self.btn_red.hit(event) and not self._bot_running:
                        self.player_color = Team.RED
                        self.btn_red.active  = True
                        self.btn_blue.active = False
                        self.new_game()
                        continue
                    if self.btn_blue.hit(event) and not self._bot_running:
                        self.player_color = Team.BLUE
                        self.btn_red.active  = False
                        self.btn_blue.active = True
                        self.new_game()
                        continue

                    # Game control buttons
                    if self.btn_new.hit(event):
                        self.new_game()
                        continue
                    if self.btn_undo.hit(event):
                        self.undo()
                        continue

                    # History nav
                    n = len(self.history)
                    if self.btn_hprev.hit(event):
                        self.hist_idx = 0
                        self.selected = None
                        self.pending_moves = []
                        self.action_btns   = []
                        self._update_status()
                        continue
                    if self.btn_prev.hit(event):
                        cur = self.hist_idx if self.hist_idx != -1 else n - 1
                        self.hist_idx = max(0, cur - 1)
                        self.selected = None
                        self.pending_moves = []
                        self.action_btns   = []
                        self._update_status()
                        continue
                    if self.btn_hnext.hit(event):
                        cur = self.hist_idx if self.hist_idx != -1 else n - 1
                        nxt = cur + 1
                        self.hist_idx = nxt if nxt < n - 1 else -1
                        self.selected = None
                        self.pending_moves = []
                        self.action_btns   = []
                        self._update_status()
                        continue
                    if self.btn_live.hit(event):
                        self.hist_idx = -1
                        self.selected = None
                        self.pending_moves = []
                        self.action_btns   = []
                        self._update_status()
                        continue

                    # Action disambiguation buttons
                    for btn in self.action_btns:
                        if btn.rect.collidepoint(pos):
                            if btn._move is None:
                                # Cancel
                                self.pending_moves = []
                                self.action_btns   = []
                                self.selected      = None
                                self.legal_for_sel = []
                            else:
                                self._execute_move(btn._move)
                                self.pending_moves = []
                                self.action_btns   = []
                            break

                    # Board click
                    rc = self._screen_to_board(pos[0], pos[1])
                    if rc is not None:
                        self._on_board_click(rc[0], rc[1])

            # Bot result check
            self._maybe_apply_bot_move()

            # Fade bot highlight after 1.5s
            if self.bot_move_highlight and time.monotonic() - self._last_bot_move_time > 1.5:
                self.bot_move_highlight = None

            # Update status periodically
            self._update_status()

            # Draw
            self._draw(mouse_pos)
            pygame.display.flip()
            self.clock.tick(30)

    # ── rendering ────────────────────────────────────────────────────────────
    def _draw(self, mouse_pos):
        surf = self.screen
        surf.fill(BG)

        self._draw_title(surf)
        self._draw_board(surf, mouse_pos)
        self._draw_captured_chips(surf)
        self._draw_panel(surf, mouse_pos)

    def _draw_title(self, surf):
        # Title bar
        pygame.draw.rect(surf, C_CARD, (0, 0, WIN_W, 56))
        pygame.draw.rect(surf, C_DIVIDER, (0, 55, WIN_W, 1))
        title = self.f_title.render('PokeChess', True, C_WHITE)
        surf.blit(title, (BOARD_X, 16))
        state = self._viewing_state()
        turn_color = C_RED if state.active_player == Team.RED else C_BLUE
        tc_name = 'RED' if state.active_player == Team.RED else 'BLUE'
        t_txt = self.f_body.render(
            f'Turn {state.turn_number}  |  Active: {tc_name}', True, turn_color)
        surf.blit(t_txt, (BOARD_X + 140, 20))

        # Status
        st = self.f_head.render(self.status_msg, True, self.status_color)
        surf.blit(st, (BOARD_X + 400, 18))

        # Bot thinking spinner
        if self._bot_running:
            t = int(time.monotonic() * 3) % 4
            dots = '.' * (t + 1) + '   '
            sp = self.f_body.render(dots[:4], True, C_CYAN)
            surf.blit(sp, (BOARD_X + 400 + st.get_width() + 8, 20))

    def _draw_board(self, surf, mouse_pos):
        state  = self._viewing_state()
        is_live = (self.hist_idx == -1)

        # Build highlight sets
        move_sqs: set   = set()
        trade_sqs: set  = set()
        attack_sqs: set = set()
        fore_sqs: set   = set()
        qa_mid_sqs: set = set()
        can_evolve: bool = False

        if self.selected and is_live:
            for m in self.legal_for_sel:
                at = m.action_type
                if at == ActionType.MOVE:
                    move_sqs.add((m.target_row, m.target_col))
                elif at in (ActionType.ATTACK, ActionType.QUICK_ATTACK):
                    tr, tc = (m.secondary_row, m.secondary_col) if at == ActionType.QUICK_ATTACK else (m.target_row, m.target_col)
                    attack_sqs.add((tr, tc))
                    if at == ActionType.QUICK_ATTACK:
                        qa_mid_sqs.add((m.target_row, m.target_col))
                elif at == ActionType.FORESIGHT:
                    fore_sqs.add((m.target_row, m.target_col))
                elif at == ActionType.TRADE:
                    trade_sqs.add((m.target_row, m.target_col))
                elif at == ActionType.EVOLVE:
                    can_evolve = True   # target == own square; signal via sel highlight

        # Draw squares
        for r in range(8):
            for c in range(8):
                sx, sy = self._board_to_screen(r, c)
                is_light = (r + c) % 2 == 0
                base_col = LIGHT_SQ if is_light else DARK_SQ
                pygame.draw.rect(surf, base_col, (sx, sy, CELL, CELL))

                # Highlights as overlays
                overlay = None
                if self.selected and (r, c) == self.selected:
                    # Green ring when evolution is available (click piece again)
                    overlay = (80, 230, 80) if can_evolve else HL_SELECT
                elif (r, c) in attack_sqs:
                    overlay = HL_ATTACK
                elif (r, c) in fore_sqs:
                    overlay = HL_FORE
                elif (r, c) in qa_mid_sqs:
                    overlay = HL_MOVE
                elif (r, c) in trade_sqs:
                    overlay = C_CYAN      # cyan for trade targets
                elif (r, c) in move_sqs:
                    overlay = HL_MOVE
                # Bot last-move highlight
                if self.bot_move_highlight:
                    fr, fc, tr, tc = self.bot_move_highlight
                    fade = max(0, 1.0 - (time.monotonic() - self._last_bot_move_time) / 1.5)
                    if (r, c) in ((fr, fc), (tr, tc)) and fade > 0:
                        a = int(fade * 120)
                        ol = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                        ol.fill((200, 200, 50, a))
                        surf.blit(ol, (sx, sy))

                if overlay:
                    ol = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                    ol.fill((*overlay, HL_ALPHA))
                    surf.blit(ol, (sx, sy))

                # Piece
                piece = state.board[r][c]
                if piece:
                    self._draw_piece(surf, piece, sx, sy, mouse_pos)

        # Board border
        brd = pygame.Rect(BOARD_X - 2, BOARD_Y - 2, 8 * CELL + 4, 8 * CELL + 4)
        pygame.draw.rect(surf, C_DIVIDER, brd, 2, border_radius=3)

        # Rank / file labels
        for i in range(8):
            # Rank numbers (left side)
            if self.player_color == Team.RED:
                rank_lbl = str(i + 1)     # board row i → label i+1 from bottom = row 0=1
                rx, ry = self._board_to_screen(i, 0)
            else:
                rank_lbl = str(8 - i)
                rx, ry = self._board_to_screen(i, 0)
            lt = self.f_coord.render(rank_lbl, True, C_DIM)
            surf.blit(lt, (rx + 2, ry + 2))
            # File letters (bottom)
            file_lbl = chr(ord('a') + i)
            fx2, fy2 = self._board_to_screen(0, i)
            ft = self.f_coord.render(file_lbl, True, C_DIM)
            surf.blit(ft, (fx2 + CELL - ft.get_width() - 2,
                           fy2 + CELL - ft.get_height() - 1))

    def _draw_piece(self, surf, piece, sx, sy, mouse_pos):
        cx = sx + CELL // 2
        cy = sy + CELL // 2 - 4

        # Team ring — thick coloured border
        ring_col = C_RED if piece.team == Team.RED else C_BLUE
        ring_r   = RING_R
        pygame.draw.circle(surf, ring_col, (cx, cy), ring_r)
        pygame.draw.circle(surf, BG,       (cx, cy), ring_r - RING_BORDER)

        if piece.piece_type in self._sprites:
            img = self._sprites[piece.piece_type]
            surf.blit(img, img.get_rect(center=(cx, cy)))
        elif piece.piece_type in (PieceType.POKEBALL, PieceType.MASTERBALL,
                                   PieceType.SAFETYBALL, PieceType.MASTER_SAFETYBALL):
            self._draw_ball(surf, piece, cx, cy)
        else:
            # Fallback: text label
            lbl = self.f_small.render(piece.piece_type.name[:4], True, C_WHITE)
            surf.blit(lbl, lbl.get_rect(center=(cx, cy)))

        # HP bar
        max_hp = PIECE_STATS[piece.piece_type].max_hp if piece.piece_type in PIECE_STATS else 0
        if max_hp > 0:
            bar_w = CELL - 10
            bar_h = 5
            bx = sx + 5
            by = sy + CELL - bar_h - 3
            hp_pct = max(0.0, piece.current_hp / max_hp)
            pygame.draw.rect(surf, (60, 60, 60), (bx, by, bar_w, bar_h), border_radius=2)
            if hp_pct > 0:
                fc = C_GREEN if hp_pct > 0.6 else (C_YELLOW if hp_pct > 0.3 else C_RED)
                pygame.draw.rect(surf, fc, (bx, by, int(bar_w * hp_pct), bar_h), border_radius=2)

        # Tooltip on hover
        if pygame.Rect(sx, sy, CELL, CELL).collidepoint(mouse_pos):
            max_hp = PIECE_STATS[piece.piece_type].max_hp if piece.piece_type in PIECE_STATS else 0
            hp_str = f'  HP {piece.current_hp}/{max_hp}' if max_hp > 0 else ''
            item_str = f'  [{piece.held_item.name}]' if piece.held_item != Item.NONE else ''
            king_str = ' (King)' if piece.is_king else ''
            stored = piece.stored_piece
            stored_str = (f'  [Storing: {stored.piece_type.name} {stored.current_hp}/{stored.max_hp}HP]'
                          if stored is not None else '')
            self.tooltip_text = (
                f'{PIECE_LABEL.get(piece.piece_type, "?")}'
                f'{king_str}  {"RED" if piece.team == Team.RED else "BLUE"}'
                f'{hp_str}{item_str}{stored_str}'
            )

    def _draw_chip_ball(self, surf, ptype: PieceType, cx: int, cy: int, r: int) -> None:
        """Draw a pokeball icon at (cx, cy) with radius r, styled by ptype."""
        import math
        is_master = ptype in (PieceType.MASTERBALL, PieceType.MASTER_SAFETYBALL)
        is_safety = ptype in (PieceType.SAFETYBALL, PieceType.MASTER_SAFETYBALL)
        top_col = (200, 50, 50) if not is_master else (128, 0, 180)
        bot_col = (240, 240, 240) if is_safety    else (30,  30,  30)
        line_col = (20, 20, 20)
        pygame.draw.circle(surf, bot_col, (cx, cy), r)
        pts = [(cx, cy)]
        for deg in range(0, 181, 6):
            rad = math.radians(deg)
            pts.append((cx + r * math.cos(rad), cy - r * math.sin(rad)))
        pygame.draw.polygon(surf, top_col, pts)
        pygame.draw.circle(surf, line_col, (cx, cy), r, 1)
        pygame.draw.line(surf, line_col, (cx - r, cy), (cx + r, cy), 1)
        btn_r = max(2, r // 4)
        pygame.draw.circle(surf, bot_col,  (cx, cy), btn_r)
        pygame.draw.circle(surf, line_col, (cx, cy), btn_r, 1)

    def _draw_captured_chips(self, surf) -> None:
        """Draw two rows of piece chips below the board (one row per team's losses)."""
        chip_spacing = CHIP_R * 2 + 3
        label_w      = 24
        base_y       = BOARD_Y + 8 * CELL + CHIP_R + 8   # first row centre

        for row_idx, (team, color) in enumerate(
            [(Team.RED, C_RED), (Team.BLUE, C_BLUE)]
        ):
            y_center = base_y + row_idx * (CHIP_R * 2 + 6)

            lbl = self.f_small.render('R×' if team == Team.RED else 'B×', True, color)
            surf.blit(lbl, (BOARD_X, y_center - lbl.get_height() // 2))

            x = BOARD_X + label_w
            for ptype in self._captures[team]:
                cx = x + CHIP_R
                pygame.draw.circle(surf, color, (cx, y_center), CHIP_R)
                pygame.draw.circle(surf, BG,    (cx, y_center), CHIP_INNER_R)
                chip_spr = self._chip_sprites.get(ptype)
                if chip_spr:
                    surf.blit(chip_spr, chip_spr.get_rect(center=(cx, y_center)))
                else:
                    self._draw_chip_ball(surf, ptype, cx, y_center, CHIP_INNER_R)
                x += chip_spacing

    def _draw_ball(self, surf, piece, cx, cy):
        import math
        is_master  = piece.piece_type in (PieceType.MASTERBALL, PieceType.MASTER_SAFETYBALL)
        is_safety  = piece.piece_type in (PieceType.SAFETYBALL, PieceType.MASTER_SAFETYBALL)
        r          = RING_R - 4   # pokeball fills the ring's inner circle
        top_col    = (200, 50, 50) if not is_master else (128, 0, 180)
        bot_col    = (240, 240, 240) if is_safety    else (30, 30, 30)
        line_col   = (20, 20, 20)

        # Full circle in bottom colour, then top semicircle in top colour
        pygame.draw.circle(surf, bot_col, (cx, cy), r)
        # Top half polygon: centre + arc from 0° to 180° (standard math, y-flipped)
        pts = [(cx, cy)]
        for deg in range(0, 181, 3):
            rad = math.radians(deg)
            pts.append((cx + r * math.cos(rad), cy - r * math.sin(rad)))
        pygame.draw.polygon(surf, top_col, pts)
        # Master balls: 'M' label on the upper half
        if is_master:
            font = pygame.font.SysFont('Arial', r, bold=True)
            lbl  = font.render('M', True, (240, 240, 255))
            surf.blit(lbl, lbl.get_rect(center=(cx, cy - r // 2)))
        # Circle border
        pygame.draw.circle(surf, line_col, (cx, cy), r, 2)
        # Horizontal dividing line
        pygame.draw.line(surf, line_col, (cx - r, cy), (cx + r, cy), 2)
        # Centre button
        btn_r = 7
        pygame.draw.circle(surf, bot_col,  (cx, cy), btn_r)
        pygame.draw.circle(surf, line_col, (cx, cy), btn_r, 2)

    def _draw_panel(self, surf, mouse_pos):
        # Panel background
        pygame.draw.rect(surf, C_PANEL,
                         (PANEL_X - 10, 0, PANEL_W + 20, WIN_H))
        pygame.draw.rect(surf, C_DIVIDER, (PANEL_X - 10, 0, 1, WIN_H))

        px = PANEL_X
        bar_w = PANEL_W - 4   # PANEL_W already has 30px right margin baked in

        # ── Section: HP balance bar ────────────────────────────────────────
        state = self._viewing_state()
        red_hp  = self._team_hp(state, Team.RED)
        blue_hp = self._team_hp(state, Team.BLUE)
        total_hp = red_hp + blue_hp

        hp_lbl = self.f_small.render('Total HP', True, C_DIM)
        surf.blit(hp_lbl, (px, 4))

        bar_x, bar_y, bar_h = px, 18, 12
        pygame.draw.rect(surf, C_DIVIDER, (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        if total_hp > 0:
            red_w = int(bar_w * red_hp / total_hp)
            if red_w > 0:
                pygame.draw.rect(surf, C_RED,  (bar_x, bar_y, red_w, bar_h),
                                 border_radius=4)
            if bar_w - red_w > 0:
                pygame.draw.rect(surf, C_BLUE, (bar_x + red_w, bar_y, bar_w - red_w, bar_h),
                                 border_radius=4)
        red_hp_lbl  = self.f_small.render(f'R {red_hp}', True, C_RED)
        blue_hp_lbl = self.f_small.render(f'B {blue_hp}', True, C_BLUE)
        surf.blit(red_hp_lbl,  (bar_x, bar_y + bar_h + 2))
        surf.blit(blue_hp_lbl, (bar_x + bar_w - blue_hp_lbl.get_width(), bar_y + bar_h + 2))

        pygame.draw.rect(surf, C_DIVIDER, (px, 44, bar_w, 1))

        # ── Section: Color choice ──────────────────────────────────────────
        lbl = self.f_head.render('You play as:', True, C_DIM)
        surf.blit(lbl, (px, 68))
        self.btn_red.draw(surf, mouse_pos)
        self.btn_blue.draw(surf, mouse_pos)

        # ── Section: Bot settings ─────────────────────────────────────────
        pygame.draw.rect(surf, C_DIVIDER, (px, 138, PANEL_W - 10, 1))
        bl = self.f_head.render('Bot Settings', True, C_DIM)
        surf.blit(bl, (px, 144))
        self.sl_budget.draw(surf)
        self.sl_tt.draw(surf)

        # TT stats — placed BELOW sl_tt track (track is at sl_tt.y+30 = 245, knob r=9 → bottom at 254)
        tt_entries = len(self.shared_tt)
        tt_txt = self.f_small.render(
            f'TT entries: {tt_entries:,}  (grows across games)', True, C_DIM)
        surf.blit(tt_txt, (px, 258))

        # ── Section: Controls ─────────────────────────────────────────────
        pygame.draw.rect(surf, C_DIVIDER, (px, 270, PANEL_W - 10, 1))
        self.btn_new.draw(surf, mouse_pos)
        self.btn_undo.draw(surf, mouse_pos)

        # History nav
        n = len(self.history)
        cur_h = self.hist_idx if self.hist_idx != -1 else n - 1
        h_lbl = self.f_small.render(
            f'History: [{cur_h + 1}/{n}]',
            True, C_DIM)
        surf.blit(h_lbl, (px, 318))
        self.btn_hprev.draw(surf, mouse_pos)
        self.btn_prev.draw(surf, mouse_pos)
        self.btn_hnext.draw(surf, mouse_pos)
        self.btn_live.draw(surf, mouse_pos)

        # ── Section: Action / disambiguation OR selected info + log ──────
        pygame.draw.rect(surf, C_DIVIDER, (px, 352, PANEL_W - 10, 1))

        if self.pending_moves or self.action_btns:
            # Disambiguation panel takes over the lower half — log is hidden
            al = self.f_head.render('Choose action:', True, C_YELLOW)
            surf.blit(al, (px, 356))
            for btn in self.action_btns:
                btn.draw(surf, mouse_pos)
        else:
            # Selected piece info (if any)
            info_y = 356
            if self.selected:
                sr, sc = self.selected
                s  = self._viewing_state()
                piece = s.board[sr][sc]
                if piece:
                    pname  = PIECE_LABEL.get(piece.piece_type, '?')
                    max_hp = PIECE_STATS[piece.piece_type].max_hp if piece.piece_type in PIECE_STATS else 0
                    sel_col = C_GREEN if any(m.action_type == ActionType.EVOLVE
                                              for m in self.legal_for_sel) else C_YELLOW
                    sl = self.f_head.render(
                        f'Selected: {pname}  HP {piece.current_hp}/{max_hp}', True, sel_col)
                    surf.blit(sl, (px, info_y))
                    hints = []
                    if any(m.action_type == ActionType.EVOLVE for m in self.legal_for_sel):
                        hints.append('click piece again to evolve')
                    if any(m.action_type == ActionType.TRADE for m in self.legal_for_sel):
                        hints.append('cyan = trade')
                    hint_str = '  |  '.join(hints) if hints else 'click a highlighted square'
                    nl = self.f_small.render(
                        f'{len(self.legal_for_sel)} moves — {hint_str}', True, C_DIM)
                    surf.blit(nl, (px, info_y + 18))
                    info_y += 38

            # Move log
            log_y = info_y + 8
            pygame.draw.rect(surf, C_DIVIDER, (px, log_y - 6, PANEL_W - 10, 1))
            ll = self.f_small.render('Move log', True, C_DIM)
            surf.blit(ll, (px, log_y - 18))
            self.log_widget.rect.y = log_y
            self.log_widget.rect.h = WIN_H - log_y - 10
            self.log_widget.draw(surf, mouse_pos)

        # ── Tooltip ───────────────────────────────────────────────────────
        if self.tooltip_text:
            tip = self.f_small.render(self.tooltip_text, True, C_WHITE)
            tw, th = tip.get_size()
            tx = min(mouse_pos[0] + 12, WIN_W - tw - 6)
            ty = min(mouse_pos[1] + 12, WIN_H - th - 6)
            bg = pygame.Surface((tw + 8, th + 4))
            bg.fill((20, 20, 30))
            bg.set_alpha(220)
            surf.blit(bg, (tx - 4, ty - 2))
            surf.blit(tip, (tx, ty))
            self.tooltip_text = ''

        # ── Game-over overlay ─────────────────────────────────────────────
        done, winner = is_terminal(self._live_state())
        if done:
            s2 = self.f_head.render('Game over  —  press New Game to play again',
                                    True, C_YELLOW)
            surf.blit(s2, (BOARD_X, BOARD_Y + 8 * CELL + 8))


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='PokeChess — play against the MCTS bot')
    ap.add_argument('--budget', type=float, default=1.0,
                    help='Initial bot time budget in seconds (default 1.0)')
    args = ap.parse_args()
    PokeChessApp(init_budget=args.budget).run()


if __name__ == '__main__':
    main()
