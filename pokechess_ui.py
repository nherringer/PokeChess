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

from engine.state import GameState, Team, PieceType, Item, PIECE_STATS, PAWN_TYPES, KING_TYPES, MATCHUP, PokemonType
from engine.moves import get_legal_moves, Move, ActionType
from engine.rules import apply_move, is_terminal, hp_winner
from bot.mcts import MCTS
from bot.transposition import TranspositionTable
from bot.persona import ALL_PERSONAS, Persona
from bot.ucb import DEFAULT_C

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
    ActionType.PSYWAVE:      'Psywave',
}

MEW_SLOTS  = {0: 'Fire Blast', 1: 'Hydro Pump', 2: 'Solar Beam'}
EVO_SLOTS  = {0: 'Vaporeon', 1: 'Flareon', 2: 'Leafeon', 3: 'Jolteon', 4: 'Espeon'}

# Tall grass rows (API coordinates)
TALL_GRASS_ROWS = frozenset([2, 3, 4, 5])

# Item display: abbreviated label + color for board and badge rendering
ITEM_DISPLAY: dict = {
    Item.WATERSTONE:   ('WS', (100, 200, 255)),
    Item.FIRESTONE:    ('FS', (255, 120,  40)),
    Item.LEAFSTONE:    ('LS', ( 80, 210,  80)),
    Item.THUNDERSTONE: ('TS', (255, 230,  30)),
    Item.BENTSPOON:    ('BS', (200, 100, 255)),
}


# ──────────────────────────────────────────────────────────────────────────────
# Persona display metadata
# ──────────────────────────────────────────────────────────────────────────────
PERSONA_COLORS = {
    'Bonnie':       (100, 210,  90),
    'Team Rocket':  (190,  45,  45),
    'Serena':       ( 90, 150, 230),
    'Clemont':      (230, 195,  45),
    'Diantha':      (185,  85, 225),
    'METALLIC':     (195, 205, 220),
}

# Flavor text shown on each persona card.
# Team Rocket and Clemont explicitly state their forced team.
PERSONA_FLAVOR = {
    'Bonnie':
        '"I\'ll take care of you! Dedenne, let\'s go!"',
    'Team Rocket':
        '"Prepare for trouble! We\'ll snatch your Pikachu!\n'
        '⚠ You will play as RED (Pikachu\'s side).',
    'Serena':
        '"A true performer never shows weakness. En garde."',
    'Clemont':
        '"The science of my strategy is PERFECT! I guarantee it!\n'
        '⚠ You will play as BLUE (Clemont keeps Pikachu\'s side).',
    'Diantha':
        '"I look forward to seeing what you can do. Truly."',
    'METALLIC':
        '"MATCH INITIATED. OUTCOME PREDETERMINED. RESISTANCE FUTILE."',
}

PERSONA_STARS = {
    'Bonnie': 1, 'Team Rocket': 2, 'Serena': 3,
    'Clemont': 4, 'Diantha': 5, 'METALLIC': 6,
}

# Trainer sprite filenames (in SPRITE_DIR).  METALLIC uses Mew with silver tint.
PERSONA_SPRITE_FILE = {
    'Bonnie':      'bonnie.png',
    'Team Rocket': 'teamrocket.png',
    'Serena':      'serena.png',
    'Clemont':     'clemont.png',
    'Diantha':     'diantha-masters.png',
    'METALLIC':    'METALLIC.jpg',
}

# Personas that force a specific player team.
# Value = the team the PLAYER must be (bot takes the other).
PERSONA_FORCED_PLAYER = {
    'Team Rocket': 'RED',    # bot hunts Pikachu → player must hold Pikachu (RED)
    'Clemont':     'BLUE',   # bot plays Pikachu side (RED) → player is BLUE
}

# ──────────────────────────────────────────────────────────────────────────────
# Persona chat message banks
# Keys: 'idle' | 'capture' | 'miss' | 'evolve' | 'foresight' | 'win' | 'loss'
# ──────────────────────────────────────────────────────────────────────────────
PERSONA_CHAT: dict = {
    'Bonnie': {
        'idle':      [
            "Your Pokemon are SO cute, but I'm still gonna win!",
            "Dedenne says you're playing pretty good... but not good enough!",
            "Heehee, are you nervous? I am a little bit!",
            "My brother Clemont taught me some tricks. Watch out!",
            "I believe in my Pokemon! Do you believe in yours?",
        ],
        'capture':   [
            "Gotcha! Your Pokemon is mine now — don't cry!",
            "Yaaaay! I caught one! Dedenne, did you see that?!",
            "Oopsie for you! That Pokemon is on MY side now!",
        ],
        'miss':      [
            "Nooo! It got away! That's not fair!",
            "Hmph! I wasn't ready anyway. I'll get it next time!",
            "The Pokeball missed... Dedenne is very upset about this.",
        ],
        'evolve':    [
            "WHOAAAA! Your Pokemon evolved!! That looks so cool though...",
            "An evolution?! That's amazing! I want one too!!",
            "Wow wow WOW! Even evolved it won't beat me!",
        ],
        'foresight': [
            "Ooh, a Foresight! I learned about that from a book!",
            "That Foresight is kinda scary... I'll deal with it!",
        ],
        'win':       [
            "YAY YAY YAY! I WON! Dedenne, we did it!!!",
            "Heehee! I told you I'd win! You were great though!",
        ],
        'loss':      [
            "Aww... you're really really good... I'll train more!",
            "I lost... but just you wait! I'll get stronger!",
        ],
    },
    'Team Rocket': {
        'idle':      [
            "Prepare for trouble — and make it DOUBLE! Nyahaha!",
            "That Pikachu is as good as ours, twerp.",
            "Team Rocket is watching your every move. Don't get comfortable.",
            "Meowth, that's right! We've got a strategy you can't stop!",
            "We've been blasting off for years. A little chess won't stop us.",
        ],
        'capture':   [
            "MAKE IT DOUBLE! Another Pokemon falls into Team Rocket's hands!",
            "Jessie: Beautiful! James: Magnificent! Meowth: Dat's right!",
            "To protect the world from devastation — and steal your pieces!",
        ],
        'miss':      [
            "WOBBUFFET! How did that one escape our magnificent trap?!",
            "A setback! But Team Rocket NEVER gives up, twerp!",
            "Grr... we'll get that Pokemon if it's the last thing we do!",
        ],
        'evolve':    [
            "An evolution?! How DARE you power up against Team Rocket!",
            "Ugh! Even stronger now? This wasn't in the plan!",
        ],
        'foresight': [
            "Oho! A Foresight? Even Team Rocket appreciates a cunning plot!",
            "Setting traps, are we? We invented that move, twerp.",
        ],
        'win':       [
            "Team Rocket wins! Prepare for trouble — WE WON! NYAHAHA!",
            "Jessie: We're BRILLIANT! James: Utterly magnificent! Meowth: We're rich!",
        ],
        'loss':      [
            "We're blasting off AGAIN! ...This isn't over, twerp!!",
            "Retreat! RETREAT! We'll be back... we ALWAYS come back!",
        ],
    },
    'Serena': {
        'idle':      [
            "Hmm. A decent move. But real battles need style too.",
            "I've been watching. You're better than most challengers.",
            "Every performer knows when to strike with flair. Like this.",
            "Grace under pressure — that's what separates good from great.",
            "My Braixen would approve of that technique. Barely.",
        ],
        'capture':   [
            "Beautiful. Like a well-rehearsed performance piece.",
            "And scene! That capture was utterly flawless.",
            "The crowd goes wild. Elegant as always.",
        ],
        'miss':      [
            "Even the best performers have unexpected moments. Move on.",
            "Oh? It escaped? Every routine has its improvisations.",
            "Hmph. Not my finest showcase. I'll recalibrate.",
        ],
        'evolve':    [
            "An evolution! Even more dazzling. This just got interesting.",
            "How gorgeous. Evolution is the ultimate performance.",
        ],
        'foresight': [
            "Planning several steps ahead? I see we think alike.",
            "Foresight — the mark of a true strategist.",
        ],
        'win':       [
            "And that's a perfect score. The audience is on their feet.",
            "Graceful from start to finish. That's my style.",
        ],
        'loss':      [
            "...Remarkable. You've genuinely surprised me.",
            "I'll admit it — well played. Truly.",
        ],
    },
    'Clemont': {
        'idle':      [
            "The science of this battle is absolutely FASCINATING!",
            "I've calculated your next 3 moves and prepared accordingly. Probably.",
            "Did you know the optimal MCTS exploration constant is sqrt(2)? I use that!",
            "My Aipom Arm invention would be really useful right now...",
            "The electric type has a 2x effectiveness against water. SCIENCE!",
        ],
        'capture':   [
            "EUREKA! That capture's efficiency is statistically remarkable!",
            "The science of pokeballs never fails to amaze me! CAUGHT!",
            "I calculated a 73.6% capture probability! It worked! IT WORKED!",
        ],
        'miss':      [
            "Hmm. A 47.3% failure rate on that attempt. Recalibrating...",
            "The math said it should work! Why doesn't the math work?!",
            "...Variance. Every good scientist accounts for variance.",
        ],
        'evolve':    [
            "The SCIENCE of evolution is breathtaking! Updated threat model!",
            "An evolution! I need to recalculate EVERYTHING!",
        ],
        'foresight': [
            "Ooh, a Foresight! The delayed-action mechanic is so elegant!",
            "Planning a future attack? I invented a device that does that!",
        ],
        'win':       [
            "I accounted for every variable! The science of victory is MINE!",
            "EUREKA! My calculations were PERFECT! Science wins again!",
        ],
        'loss':      [
            "Im...impossible. My calculations were flawless! There must be a bug!",
            "Defeated?! I need to go invent something to process this loss.",
        ],
    },
    'Diantha': {
        'idle':      [
            "You're performing admirably. This is a genuinely interesting match.",
            "I've faced many challengers. Fewer surprise me. You might.",
            "Take your time. I've waited years for a battle worth having.",
            "Your intuition is strong. I can see why you came this far.",
            "Even in defeat, there is something to be learned. For both of us.",
        ],
        'capture':   [
            "Clean. Decisive. That's the mark of a real trainer.",
            "Beautifully handled. No hesitation.",
            "Elegant. You executed that with the calm of a champion.",
        ],
        'miss':      [
            "Even certain things slip away. That's the nature of this game.",
            "How... fleeting. Though nothing is truly lost yet.",
            "A miss. But your instinct to try was correct.",
        ],
        'evolve':    [
            "Beautiful. Every evolution is a work of art in motion.",
            "Magnificent. Your bond with that Pokemon is evident.",
        ],
        'foresight': [
            "Foresight. You think ahead. That quality will serve you well.",
            "Setting the board for what comes next. A Kalos champion's move.",
        ],
        'win':       [
            "A worthy battle. You challenged me more than most ever do.",
            "Well fought. Come back when you've grown — I'll be waiting.",
        ],
        'loss':      [
            "...Well done. You have earned the right to call yourself a champion.",
            "I don't lose often. Remember this feeling — it matters.",
        ],
    },
    'METALLIC': {
        'idle':      [
            "ANALYSIS COMPLETE. OPTIMAL MOVE SELECTED. RESISTANCE FUTILE.",
            "THREAT ASSESSMENT: MODERATE. ADJUSTING PARAMETERS.",
            "WIN PROBABILITY: CALCULATED. OUTCOME: PREDETERMINED.",
            "PROCESSING. YOUR MOVE WAS WITHIN EXPECTED PARAMETERS.",
            "OBSERVATION: YOU ARE ATTEMPTING TO COUNTER MY STRATEGY. NOTED. IRRELEVANT.",
        ],
        'capture':   [
            "TARGET ELIMINATED. WIN PROBABILITY INCREASED BY 3.7%.",
            "CAPTURE SUCCESSFUL. THREAT MATRIX UPDATED.",
            "UNIT NEUTRALIZED. PROCESSING NEXT TARGET.",
        ],
        'miss':      [
            "LOW-PROBABILITY EVENT MATERIALIZED. RECALIBRATING.",
            "UNEXPECTED OUTCOME. ERROR MARGIN: 0.001%. ACCEPTABLE.",
            "PROBABILITY: 12.4%. EVENT OCCURRED. ADAPTING.",
        ],
        'evolve':    [
            "EVOLUTION DETECTED. THREAT LEVEL UPDATED. STRATEGY UNCHANGED.",
            "TARGET HAS EVOLVED. NEW THREAT MODEL LOADED. PROCEED.",
        ],
        'foresight': [
            "FORESIGHT REGISTERED. COUNTER-SEQUENCE INITIATED.",
            "DELAYED ATTACK NOTED. EVASION PROBABILITY CALCULATED.",
        ],
        'win':       [
            "MATCH CONCLUDED. OUTCOME: METALLIC WINS. AS CALCULATED.",
            "VICTORY CONFIRMED. ALL VARIABLES WITHIN PREDICTED BOUNDS.",
        ],
        'loss':      [
            "UNEXPECTED RESULT. ANALYZING ANOMALY FOR FUTURE REFERENCE.",
            "DEFEAT REGISTERED. THIS DATA WILL IMPROVE FUTURE PERFORMANCE.",
        ],
    },
}


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
# Landing screen
# ──────────────────────────────────────────────────────────────────────────────
class LandingScreen:
    """Pre-game screen: logo, mode selection, persona picker, team colour."""


    def __init__(self):
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        pygame.display.set_caption('PokeChess')
        self.clock = pygame.time.Clock()

        self.f_chess  = pygame.font.SysFont('Arial', 68, bold=True)
        self.f_hero   = pygame.font.SysFont('Arial', 44, bold=True)
        self.f_head   = pygame.font.SysFont('Arial', 15, bold=True)
        self.f_body   = pygame.font.SysFont('Arial', 13)
        self.f_small  = pygame.font.SysFont('Arial', 11)
        self.f_mode   = pygame.font.SysFont('Arial', 17, bold=True)

        # State
        self._mode:         Optional[str]     = None   # 'bot' | 'local'
        self._persona:      Optional[Persona] = None
        self._player_color: Team              = Team.RED

        # ── POKE logo image ──────────────────────────────────────────────────
        # ── POKE logo image ──────────────────────────────────────────────────
        _BOLT_H = 120   # lightning bolt display height (drives logo scale)

        poke_path = os.path.join(SPRITE_DIR, 'POKE.png')
        raw_poke = pygame.image.load(poke_path).convert_alpha()
        # Measure CHESS block width so POKE takes up the same horizontal space
        _f_chess_tmp = pygame.font.SysFont('Arial', 68, bold=True)
        _chess_sample = [_f_chess_tmp.render(ch, True, (255, 255, 255)) for ch in 'CHESS']
        _chess_tile_w_init = max(s.get_width() for s in _chess_sample) + 6 * 2
        _chess_w_init = _chess_tile_w_init * 5
        # Scale POKE so its width matches chess_w; height follows aspect ratio
        poke_w = _chess_w_init
        poke_h = int(raw_poke.get_height() * poke_w / raw_poke.get_width())
        self._poke_img = pygame.transform.smoothscale(raw_poke, (poke_w, poke_h))

        # ── Lightning bolt image (numpy BG removal → yellow tint) ───────────
        import numpy as _np
        from PIL import Image as _PILImage
        bolt_path = os.path.join(SPRITE_DIR, 'lightningbolt.jpg')
        _pil = _PILImage.open(bolt_path).convert('RGB')
        _arr = _np.array(_pil, dtype=_np.float32)
        _avg = _arr.mean(axis=2)
        _is_bg = _avg > 245.0
        _brightness = _np.clip(1.0 - (_avg / 255.0) * 0.6, 0.4, 1.0)
        _rgba = _np.zeros((_arr.shape[0], _arr.shape[1], 4), dtype=_np.uint8)
        _rgba[:, :, 0] = _np.where(_is_bg, 0, _np.clip(255 * _brightness, 0, 255).astype(_np.uint8))
        _rgba[:, :, 1] = _np.where(_is_bg, 0, _np.clip(220 * _brightness, 0, 255).astype(_np.uint8))
        _rgba[:, :, 2] = _np.where(_is_bg, 0, 30).astype(_np.uint8)
        _rgba[:, :, 3] = _np.where(_is_bg, 0, 255).astype(_np.uint8)
        _pil_rgba = _PILImage.fromarray(_rgba, 'RGBA')
        _full_surf = pygame.image.fromstring(_pil_rgba.tobytes(), _pil.size, 'RGBA').convert_alpha()
        bolt_w = int(_full_surf.get_width() * _BOLT_H / _full_surf.get_height())
        self._bolt_img = pygame.transform.smoothscale(_full_surf, (bolt_w, _BOLT_H))
        self._bolt_h   = _BOLT_H

        # ── Pikachu / Eevee landing flanking images ──────────────────────────
        # Pikachu: remove white BG via numpy, scale to 185px (slightly larger)
        # Eevee: webp with transparent BG, scale to 155px
        self._pikachu_landing: Optional[pygame.Surface] = None
        self._eevee_landing:   Optional[pygame.Surface] = None

        _pika_path = os.path.join(SPRITE_DIR, 'PikachuLandingPic.jpg')
        if os.path.exists(_pika_path):
            try:
                import numpy as _np2
                from PIL import Image as _PILImage2
                from collections import deque as _deque
                _pil_pk = _PILImage2.open(_pika_path).convert('RGB')
                _arr_pk = _np2.array(_pil_pk, dtype=_np2.float32)
                _avg_pk = _arr_pk.mean(axis=2)
                _ph, _pw = _avg_pk.shape
                # BFS flood-fill from all edge pixels to identify BACKGROUND only
                # (preserves white pixels enclosed within the sprite, like eyes)
                _visited = _np2.zeros((_ph, _pw), dtype=bool)
                _q = _deque()
                for _r in range(_ph):
                    for _c in [0, _pw - 1]:
                        if _avg_pk[_r, _c] > 220 and not _visited[_r, _c]:
                            _visited[_r, _c] = True
                            _q.append((_r, _c))
                for _c in range(_pw):
                    for _r in [0, _ph - 1]:
                        if _avg_pk[_r, _c] > 220 and not _visited[_r, _c]:
                            _visited[_r, _c] = True
                            _q.append((_r, _c))
                while _q:
                    _r, _c = _q.popleft()
                    for _dr, _dc in ((-1,0),(1,0),(0,-1),(0,1)):
                        _nr, _nc = _r+_dr, _c+_dc
                        if 0 <= _nr < _ph and 0 <= _nc < _pw and not _visited[_nr, _nc] and _avg_pk[_nr, _nc] > 210:
                            _visited[_nr, _nc] = True
                            _q.append((_nr, _nc))
                # --- Phase 2: remove large enclosed white regions (arm/tail triangles) ---
                # Triangles are 40-50px from the nearest background edge — no dilation
                # radius is feasible. Instead, label connected components of enclosed
                # near-white pixels and remove any region larger than ~400px (triangles
                # are ~1000-2000px; eyes are ~200px so they are preserved).
                _near_white_pk = _avg_pk > 228
                _enclosed_pk   = _near_white_pk & ~_visited
                _labeled_pk    = _np2.zeros((_ph, _pw), dtype=_np2.int32)
                _comp_id_pk    = 0
                _comp_sizes_pk: dict = {}
                for _sr in range(_ph):
                    for _sc in range(_pw):
                        if _enclosed_pk[_sr, _sc] and _labeled_pk[_sr, _sc] == 0:
                            _comp_id_pk += 1
                            _bfs2 = _deque([((_sr, _sc))])
                            _labeled_pk[_sr, _sc] = _comp_id_pk
                            _sz2 = 0
                            while _bfs2:
                                _r2, _c2 = _bfs2.popleft()
                                _sz2 += 1
                                for _dr2, _dc2 in ((-1,0),(1,0),(0,-1),(0,1)):
                                    _nr2, _nc2 = _r2+_dr2, _c2+_dc2
                                    if (0 <= _nr2 < _ph and 0 <= _nc2 < _pw
                                            and _enclosed_pk[_nr2, _nc2]
                                            and _labeled_pk[_nr2, _nc2] == 0):
                                        _labeled_pk[_nr2, _nc2] = _comp_id_pk
                                        _bfs2.append((_nr2, _nc2))
                            _comp_sizes_pk[_comp_id_pk] = _sz2
                # Fold large enclosed blobs (triangles) into the background mask
                _TRIANGLE_THRESH = 400
                for _cid2, _csz in _comp_sizes_pk.items():
                    if _csz > _TRIANGLE_THRESH:
                        _visited |= (_labeled_pk == _cid2)
                # --- Phase 3: small dilation to catch thin edge fringe pixels ---
                from PIL import ImageFilter as _IF
                _bg_mask_pil = _PILImage2.fromarray(_visited.astype(_np2.uint8) * 255, 'L')
                _bg_dilated  = _np2.array(_bg_mask_pil.filter(_IF.MaxFilter(9))) > 127
                # Only apply dilated mask to near-white pixels (grey/colored pixels kept)
                _is_bg_pk = _bg_dilated & (_avg_pk > 228)
                _rgba_pk = _np2.zeros((_ph, _pw, 4), dtype=_np2.uint8)
                _rgba_pk[:, :, :3] = _arr_pk.astype(_np2.uint8)
                _rgba_pk[:, :, 3] = _np2.where(_is_bg_pk, 0, 255).astype(_np2.uint8)
                _pil_pk_rgba = _PILImage2.fromarray(_rgba_pk, 'RGBA')
                _pk_surf = pygame.image.fromstring(_pil_pk_rgba.tobytes(), _pil_pk.size, 'RGBA').convert_alpha()
                _PIKA_H = 185
                _pk_w = max(1, int(_pk_surf.get_width() * _PIKA_H / _pk_surf.get_height()))
                self._pikachu_landing = pygame.transform.smoothscale(_pk_surf, (_pk_w, _PIKA_H))
            except Exception:
                pass

        _eevee_path = os.path.join(SPRITE_DIR, 'EeveeLandingPic.webp')
        if os.path.exists(_eevee_path):
            try:
                _raw_ev = pygame.image.load(_eevee_path)
                _ev = _raw_ev.convert_alpha() if _raw_ev.get_alpha() is not None else _raw_ev.convert()
                _EEVEE_H = 155
                _ev_w = max(1, int(_ev.get_width() * _EEVEE_H / _ev.get_height()))
                self._eevee_landing = pygame.transform.smoothscale(_ev, (_ev_w, _EEVEE_H))
            except Exception:
                pass

        # ── Trainer sprites ──────────────────────────────────────────────────
        self._trainer_imgs: Dict[str, pygame.Surface] = {}
        _TBOX = 80   # bounding box for each trainer portrait in card
        for name, fname in PERSONA_SPRITE_FILE.items():
            path = os.path.join(SPRITE_DIR, fname)
            if not os.path.exists(path):
                continue
            raw = pygame.image.load(path)
            # Normalise to RGBA (palette-mode PNGs and JPEGs need explicit convert)
            img = raw.convert_alpha() if raw.get_alpha() is not None else raw.convert()
            # For JPEG/opaque images, wrap in an RGBA surface so alpha ops work
            if img.get_alpha() is None:
                rgba = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                rgba.blit(img, (0, 0))
                img = rgba
            # Crop transparent padding (skip for opaque images — bounding_rect is wrong)
            if raw.get_alpha() is not None:
                bb = img.get_bounding_rect()
                if bb.width > 0 and bb.height > 0:
                    cropped = pygame.Surface((bb.width, bb.height), pygame.SRCALPHA)
                    cropped.blit(img, (0, 0), bb)
                    img = cropped
            # Scale to fit within _TBOX×_TBOX, preserving aspect ratio
            iw, ih = img.get_size()
            scale = min(_TBOX / iw, _TBOX / ih)
            sw, sh = max(1, int(iw * scale)), max(1, int(ih * scale))
            scaled = pygame.transform.smoothscale(img, (sw, sh))
            # Centre on a fixed canvas
            canvas = pygame.Surface((_TBOX, _TBOX), pygame.SRCALPHA)
            cx_off = (_TBOX - sw) // 2
            cy_off = (_TBOX - sh) // 2
            canvas.blit(scaled, (cx_off, cy_off))
            self._trainer_imgs[name] = canvas

        # ── Mode buttons ─────────────────────────────────────────────────────
        cx = WIN_W // 2
        self.btn_pvb = Button(cx - 185, 208, 170, 50, 'Kalos Characters',
                              font=self.f_mode, corner_radius=8)
        self.btn_pvp = Button(cx +  15, 208, 170, 50, 'Friends',
                              font=self.f_mode, corner_radius=8)

        # ── Persona cards (3 × 2 grid) ───────────────────────────────────────
        self._card_w, self._card_h = 355, 92
        self._card_gap             = 12
        cols                       = 3
        total_w = cols * self._card_w + (cols - 1) * self._card_gap
        self._grid_x = (WIN_W - total_w) // 2
        self._grid_y = 302

        # ── Colour toggle buttons ─────────────────────────────────────────────
        self.btn_red  = Button(cx - 110, 582, 95, 30, 'Play RED',
                               font=self.f_body, corner_radius=6)
        self.btn_blue = Button(cx +  15, 582, 95, 30, 'Play BLUE',
                               font=self.f_body, corner_radius=6)
        self.btn_red.active = True

        # ── Start button ──────────────────────────────────────────────────────
        self.btn_start = Button(cx - 90, 632, 180, 48, 'Start Game',
                                color=(45, 130, 60), hover_color=(60, 165, 78),
                                text_color=C_WHITE, font=self.f_mode, corner_radius=10)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _draw_lightning(self, surf, cx, cy, h, color=C_YELLOW):
        """Draw a lightning-bolt polygon centred at (cx, cy) with total height h."""
        w = h * 0.50
        pts = [
            (cx + w * 0.28,  cy - h * 0.50),
            (cx - w * 0.12,  cy - h * 0.02),
            (cx + w * 0.18,  cy - h * 0.02),
            (cx - w * 0.28,  cy + h * 0.50),
            (cx + w * 0.12,  cy + h * 0.02),
            (cx - w * 0.18,  cy + h * 0.02),
        ]
        pygame.draw.polygon(surf, color, [(int(x), int(y)) for x, y in pts])

    @staticmethod
    def _truncate_text(text: str, font: pygame.font.Font, max_w: int) -> str:
        """Truncate text with ellipsis to fit within max_w pixels."""
        if font.size(text)[0] <= max_w:
            return text
        ellipsis = '…'
        while text and font.size(text + ellipsis)[0] > max_w:
            text = text[:-1]
        return text + ellipsis

    def _draw_chess_letters(self, surf, x, y, h):
        """
        Render 'CHESS' as alternating dark/light block-letter tiles.
        Returns the total width rendered.
        """
        word   = 'CHESS'
        pad    = 6      # horizontal padding inside each tile
        letter_surf = [self.f_chess.render(ch, True, C_WHITE) for ch in word]
        tile_w = max(s.get_width() for s in letter_surf) + pad * 2
        tile_h = h

        dark_bg   = (18,  20,  30)
        light_bg  = (232, 232, 232)
        dark_txt  = (18,  20,  30)
        light_txt = (232, 232, 232)

        for i, (ch, lsurf) in enumerate(zip(word, letter_surf)):
            bg_col  = dark_bg   if i % 2 == 0 else light_bg
            txt_col = light_txt if i % 2 == 0 else dark_txt
            rect = pygame.Rect(x + i * tile_w, y, tile_w, tile_h)
            pygame.draw.rect(surf, bg_col, rect, border_radius=4)
            pygame.draw.rect(surf, C_DIVIDER, rect, 1, border_radius=4)
            txt = self.f_chess.render(ch, True, txt_col)
            surf.blit(txt, txt.get_rect(center=rect.center))

        return tile_w * len(word)

    def _persona_card_rect(self, idx: int) -> pygame.Rect:
        col = idx % 3
        row = idx // 3
        x = self._grid_x + col * (self._card_w + self._card_gap)
        y = self._grid_y + row * (self._card_h + self._card_gap)
        return pygame.Rect(x, y, self._card_w, self._card_h)

    def _draw_persona_card(self, surf, idx: int, persona: Persona, mouse_pos):
        rect       = self._persona_card_rect(idx)
        pc         = PERSONA_COLORS.get(persona.name, C_WHITE)
        selected   = self._persona is persona
        hovered    = rect.collidepoint(mouse_pos)

        # Background
        if selected:
            r, g, b = pc
            pygame.draw.rect(surf, (r // 4, g // 4, b // 4), rect, border_radius=8)
            pygame.draw.rect(surf, pc, rect, 2, border_radius=8)
        elif hovered:
            pygame.draw.rect(surf, C_BTN_HOV, rect, border_radius=8)
            pygame.draw.rect(surf, C_DIVIDER,  rect, 1, border_radius=8)
        else:
            pygame.draw.rect(surf, C_CARD, rect, border_radius=8)
            pygame.draw.rect(surf, C_DIVIDER, rect, 1, border_radius=8)

        # Trainer sprite (left side)
        spr = self._trainer_imgs.get(persona.name)
        spr_w = 0
        if spr:
            sy = rect.y + (rect.height - spr.get_height()) // 2
            surf.blit(spr, (rect.x + 8, sy))
            spr_w = spr.get_width() + 14

        # Text column
        tx = rect.x + spr_w + 8
        ty = rect.y + 8

        # Name
        name_col = pc if selected else pc
        name_surf = self.f_head.render(persona.name, True, name_col)
        surf.blit(name_surf, (tx, ty))

        # Difficulty — filled/empty circles
        stars = PERSONA_STARS.get(persona.name, 0)
        sr, sg = 6, 4   # circle radius and spacing gap
        star_row_y = ty + 26
        for i in range(6):
            cx_s = tx + i * (sr * 2 + sg) + sr
            if i < stars:
                pygame.draw.circle(surf, pc, (cx_s, star_row_y), sr)
            else:
                pygame.draw.circle(surf, C_DIVIDER, (cx_s, star_row_y), sr)
                pygame.draw.circle(surf, C_DIM, (cx_s, star_row_y), sr, 1)
        # Difficulty label
        diff_labels = ['', 'Beginner', 'Sneaky', 'Balanced', 'Strategic', 'Expert', 'LEGEND']
        diff_x = tx + 6 * (sr * 2 + sg) + 6
        diff_surf = self.f_small.render(diff_labels[stars], True, C_DIM)
        surf.blit(diff_surf, (diff_x, star_row_y - diff_surf.get_height() // 2))

        # Flavor text (first line only — newline is the forced-team notice)
        _max_txt_w = rect.right - tx - 10
        flavor_lines = PERSONA_FLAVOR.get(persona.name, '').split('\n')
        fl0 = self._truncate_text(flavor_lines[0], self.f_small, _max_txt_w)
        fl_surf = self.f_small.render(fl0, True, C_DIM)
        surf.blit(fl_surf, (tx, ty + 40))
        if len(flavor_lines) > 1:
            warn_col = (220, 160, 40)
            fl1 = self._truncate_text(flavor_lines[1], self.f_small, _max_txt_w)
            w2 = self.f_small.render(fl1, True, warn_col)
            surf.blit(w2, (tx, ty + 56))

    # ── main draw ─────────────────────────────────────────────────────────────

    def _draw(self, mouse_pos):
        surf = self.screen
        surf.fill(BG)
        cx = WIN_W // 2

        # ── Logo ──────────────────────────────────────────────────────────────
        # Bolt is the vertical anchor.
        # POKE is left of bolt, its centre aligns with bolt's 1/3 height.
        # CHESS is right of bolt, its centre aligns with bolt's 2/3 height.
        bh = self._bolt_h                       # e.g. 148
        bw = self._bolt_img.get_width()

        poke_h = self._poke_img.get_height()
        poke_w = self._poke_img.get_width()

        # Measure CHESS block exactly (mirrors _draw_chess_letters tile_w calc)
        _sample_letters = [self.f_chess.render(ch, True, C_WHITE) for ch in 'CHESS']
        _chess_pad = 6
        _chess_tile_w = max(s.get_width() for s in _sample_letters) + _chess_pad * 2
        chess_h = self.f_chess.get_height()
        chess_w = _chess_tile_w * 5

        total_logo_w = poke_w + bw + chess_w
        logo_x = (WIN_W - total_logo_w) // 2

        # ── Dynamic vertical centering based on current content state ─────────
        _hero_line_h = self.f_hero.get_height()
        _tagline_h_est  = _hero_line_h * 2 + 4
        # gap_above tagline + tagline + gap_below tagline + btn + divider + content_gap
        _mode_section_h = 20 + self.btn_pvb.rect.height + 14 + 14
        _base_h = bh + 20 + _tagline_h_est + _mode_section_h
        if self._mode == 'bot':
            _extra = 15 + 16 + 2 * (self._card_h + self._card_gap)
            if self._persona is not None:
                _extra += 80
            _extra += self.btn_start.rect.height + 12
            _total_h = _base_h + _extra
        elif self._mode == 'local':
            _total_h = _base_h + 120
        else:
            _total_h = _base_h + 20
        logo_y = max(8, (WIN_H - _total_h) // 2)

        bolt_x = logo_x + poke_w
        chess_x = bolt_x + bw

        # Vertical offset: POKE centre @ 1/3, CHESS centre @ 2/3
        poke_cy  = logo_y + bh // 3
        chess_cy = logo_y + 2 * bh // 3

        poke_y  = poke_cy  - poke_h  // 2
        chess_y = chess_cy - chess_h // 2

        # Blit bolt image
        surf.blit(self._bolt_img, (bolt_x, logo_y))
        # Blit POKE
        surf.blit(self._poke_img, (logo_x, poke_y))
        # Draw CHESS block letters
        self._draw_chess_letters(surf, chess_x, chess_y, chess_h)

        # Tagline — "HEY TRAINER! / Wanna battle?" (large hero font)
        # Gap above is larger so tagline sits in the lower portion of the space
        _gap_above = 36
        _gap_below = 18
        chess_bottom = chess_cy + chess_h // 2
        tagline_y = chess_bottom + _gap_above
        hey_surf = self.f_hero.render('HEY TRAINER!', True, C_YELLOW)
        wb_surf  = self.f_hero.render('Wanna battle?', True, C_WHITE)
        tagline_h = hey_surf.get_height() + 4 + wb_surf.get_height()

        # Flanking Pikachu (left) and Eevee (right) centred on the full tagline block
        flank_cy = tagline_y + tagline_h // 2  # now correct: tagline_y is the top
        _FLANK_PAD = 14   # gap between flanker and text block
        max_text_w = max(hey_surf.get_width(), wb_surf.get_width())
        if self._pikachu_landing is not None:
            px_right = cx - max_text_w // 2 - _FLANK_PAD
            px = px_right - self._pikachu_landing.get_width()
            py = flank_cy - self._pikachu_landing.get_height() // 2
            surf.blit(self._pikachu_landing, (px, py))
        if self._eevee_landing is not None:
            ex = cx + max_text_w // 2 + _FLANK_PAD
            ey = flank_cy - self._eevee_landing.get_height() // 2
            surf.blit(self._eevee_landing, (ex, ey))

        surf.blit(hey_surf, hey_surf.get_rect(midtop=(cx, tagline_y)))
        surf.blit(wb_surf,  wb_surf.get_rect(midtop=(cx, tagline_y + hey_surf.get_height() + 4)))

        # ── Mode selection — buttons placed symmetrically below tagline ─────
        btn_y = tagline_y + tagline_h + _gap_below
        self.btn_pvb.rect.y = btn_y
        self.btn_pvp.rect.y = btn_y
        self.btn_pvb.draw(surf, mouse_pos)
        self.btn_pvp.draw(surf, mouse_pos)

        divider_y = btn_y + self.btn_pvb.rect.height + 14
        pygame.draw.rect(surf, C_DIVIDER, (80, divider_y, WIN_W - 160, 1))

        # ── PvB content ───────────────────────────────────────────────────────
        content_y = divider_y + 14   # top of content area below divider
        if self._mode == 'bot':
            pl = self.f_head.render('Choose your opponent:', True, C_DIM)
            surf.blit(pl, pl.get_rect(center=(cx, content_y)))

            # Reposition persona grid relative to content_y
            self._grid_y = content_y + 16
            for idx, persona in enumerate(ALL_PERSONAS):
                self._draw_persona_card(surf, idx, persona, mouse_pos)

            # Colour section — only show after persona is chosen
            if self._persona is not None:
                forced = PERSONA_FORCED_PLAYER.get(self._persona.name)
                col_y  = self._grid_y + 2 * (self._card_h + self._card_gap) + 14

                if forced:
                    lock_text = (
                        f'Team locked — you play {forced}  '
                        f'({"Clemont commands Pikachu" if forced == "BLUE" else "Team Rocket hunts your Pikachu"})'
                    )
                    lk = self.f_body.render(lock_text, True, (220, 160, 40))
                    surf.blit(lk, lk.get_rect(center=(cx, col_y + 10)))
                else:
                    cl = self.f_head.render('Choose your team:', True, C_DIM)
                    surf.blit(cl, cl.get_rect(center=(cx - 10, col_y + 5)))
                    col_btn_y = col_y + 22
                    self.btn_red.rect.y  = col_btn_y
                    self.btn_blue.rect.y = col_btn_y
                    self.btn_red.draw(surf, mouse_pos)
                    self.btn_blue.draw(surf, mouse_pos)

            # Start button placed below colour section
            # col_y = grid_bottom + 14; label=20px; btn_h=30px; gap=10px → total ~74px
            grid_bottom = self._grid_y + 2 * (self._card_h + self._card_gap)
            start_y = grid_bottom + (0 if self._persona is None else 80)
            self.btn_start.rect.y = start_y

        elif self._mode == 'local':
            desc = self.f_body.render(
                'Two players share this screen.  Pass the keyboard between turns.', True, C_DIM)
            surf.blit(desc, desc.get_rect(center=(cx, content_y + 30)))
            self.btn_start.rect.y = content_y + 70

        # ── Start button / hint ───────────────────────────────────────────────
        can_start = (self._mode == 'local') or (self._mode == 'bot' and self._persona is not None)
        if can_start:
            self.btn_start.draw(surf, mouse_pos)
        else:
            if self._mode is None:
                hint = 'Select a game mode above to continue.'
            else:
                hint = 'Select an opponent to continue.'
            ht = self.f_small.render(hint, True, C_DIM)
            surf.blit(ht, ht.get_rect(center=(cx, self.btn_start.rect.centery)))

    # ── event loop ────────────────────────────────────────────────────────────

    def run(self) -> Optional[dict]:
        """Return config dict {mode, persona, player_color} or None to quit."""
        while True:
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return None

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos

                    # Mode selection
                    if self.btn_pvb.hit(event):
                        self._mode = 'bot'
                        self.btn_pvb.active = True
                        self.btn_pvp.active = False

                    elif self.btn_pvp.hit(event):
                        self._mode = 'local'
                        self.btn_pvp.active = True
                        self.btn_pvb.active = False
                        self._persona = None

                    # Persona card hit
                    if self._mode == 'bot':
                        for idx, persona in enumerate(ALL_PERSONAS):
                            if self._persona_card_rect(idx).collidepoint(pos):
                                self._persona = persona
                                # Apply forced colour
                                forced = PERSONA_FORCED_PLAYER.get(persona.name)
                                if forced == 'RED':
                                    self._player_color = Team.RED
                                    self.btn_red.active  = True
                                    self.btn_blue.active = False
                                elif forced == 'BLUE':
                                    self._player_color = Team.BLUE
                                    self.btn_red.active  = False
                                    self.btn_blue.active = True
                                break

                    # Colour toggle (only active when no forced colour)
                    if (self._persona is None or
                            PERSONA_FORCED_PLAYER.get(
                                self._persona.name if self._persona else '') is None):
                        if self.btn_red.hit(event):
                            self._player_color = Team.RED
                            self.btn_red.active  = True
                            self.btn_blue.active = False
                        elif self.btn_blue.hit(event):
                            self._player_color = Team.BLUE
                            self.btn_red.active  = False
                            self.btn_blue.active = True

                    # Start
                    can_start = (self._mode == 'local') or (
                        self._mode == 'bot' and self._persona is not None)
                    if can_start and self.btn_start.hit(event):
                        return {
                            'mode':         self._mode,
                            'persona':      self._persona,
                            'player_color': self._player_color,
                        }

            self._draw(mouse_pos)
            pygame.display.flip()
            self.clock.tick(30)


# ──────────────────────────────────────────────────────────────────────────────
# Main application
# ──────────────────────────────────────────────────────────────────────────────
class PokeChessApp:
    # ── init ────────────────────────────────────────────────────────────────
    def __init__(
        self,
        init_budget:  float            = 1.0,
        mode:         str              = 'bot',
        persona:      Optional[Persona] = None,
        player_color: Team             = Team.RED,
    ):
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        pygame.display.set_caption('PokeChess')
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
        self.state: Optional[GameState]         = None
        self.history: List[GameState]           = []
        self.move_log: List[str]                = []
        self.hist_idx: int                      = -1
        self.selected: Optional[Tuple[int,int]] = None
        self.legal_for_sel: List[Move]          = []
        self.pending_moves: List[Move]          = []
        self.player_color: Team                 = player_color

        # persona & bot identity
        self._persona:  Optional[Persona] = persona
        self._bot_name: str = persona.name if persona else 'Bot'

        # resolve MCTS construction params from persona (or fallback defaults)
        if persona is not None:
            _budget  = persona.time_budget
            _c       = persona.exploration_c
            _tt      = self.shared_tt if persona.use_transposition else None
            _bias    = persona.move_bias
            _bonus   = persona.bias_bonus
            _tt_init = 1.0 if persona.use_transposition else 0.0
        else:
            _budget  = init_budget
            _c       = DEFAULT_C
            _tt      = None
            _bias    = None
            _bonus   = 0.15
            _tt_init = 1.0

        # bot state
        self._bot_result: Optional[Move]  = None
        self._bot_lock                    = threading.Lock()
        self._bot_running                 = False
        self._metalic_bot: MCTS = MCTS(
            time_budget   = _budget,
            exploration_c = _c,
            transposition = _tt,
            move_bias     = _bias,
            bias_bonus    = _bonus,
        )
        self._ponder_thread: Optional[threading.Thread] = None
        self._ponder_running: bool                      = False

        # UI state
        self.status_msg   = ''
        self.status_color = C_WHITE
        self.tooltip_text = ''
        self.bot_move_highlight: Optional[Tuple[int,int,int,int]] = None
        self._last_bot_move_time = 0.0
        self._miss_flash: Optional[Tuple[int,int,float]] = None  # (row, col, start_time)

        # game mode
        self.game_mode: str          = mode
        self._local_pass_pending     = False
        self._pass_screen_on: bool   = True

        # ── build UI widgets ─────────────────────────────────────────────────
        px = PANEL_X

        # Menu button — right side of board area, just before the right panel
        self.btn_menu = Button(BOARD_X + 8 * CELL - 82, 14, 72, 26, '← Menu',
                               font=self.f_small, corner_radius=4)

        # game mode toggle
        bot_label = f'vs {self._bot_name}'
        self.btn_vs_metalic = Button(px,     68, 120, 28, bot_label,
                                     font=self.f_body, corner_radius=6)
        self.btn_local_mode = Button(px+128, 68,  76, 28, 'Local',
                                     font=self.f_body, corner_radius=6)
        self.btn_vs_metalic.active = (self.game_mode == 'bot')
        self.btn_local_mode.active = (self.game_mode == 'local')

        # pass-screen toggle (local mode only)
        self.btn_pass_toggle = Button(px, 106, PANEL_W - 4, 24, 'Pass screen',
                                      font=self.f_body, corner_radius=5)
        self.btn_pass_toggle.active = True

        # color toggle (bot mode only)
        self.btn_red  = Button(px,      106, 100, 28, 'Play as RED',
                               font=self.f_body, corner_radius=6)
        self.btn_blue = Button(px+108,  106, 104, 28, 'Play as BLUE',
                               font=self.f_body, corner_radius=6)
        self.btn_red.active  = (player_color == Team.RED)
        self.btn_blue.active = (player_color == Team.BLUE)

        # bot sliders — kept for PvP mode; hidden in bot mode (persona fixes values)
        sx = px
        sw = PANEL_W - 4
        self.sl_budget = Slider(sx, 200, sw, 0.2, 10.0, _budget,
                                label='Bot time budget (s)',
                                fmt='{:.1f}s',
                                font=self.f_body, lbl_font=self.f_small)
        self.sl_tt     = Slider(sx, 255, sw, 0.0, 1.0, _tt_init,
                                label='TT access  (prior knowledge)',
                                fmt='{:.0%}',
                                font=self.f_body, lbl_font=self.f_small)

        # persona chat widget — replaces slider area in bot mode
        self.chat_widget = ScrollLog(px, 186, PANEL_W - 4, 120, font=self.f_log)

        # chat pacing: post a random quip every _next_chat_move moves
        self._move_count:    int = 0
        self._next_chat_move: int = random.randint(3, 7)

        # game controls
        bw = (PANEL_W - 10) // 2 - 2
        self.btn_new  = Button(px,      318, bw, 34, 'New Game',
                               font=self.f_body, corner_radius=6)
        self.btn_undo = Button(px+bw+4, 318, bw, 34, 'Undo',
                               font=self.f_body, corner_radius=6)

        # history nav
        nw = (PANEL_W - 10) // 4 - 2
        self.btn_hprev = Button(px,          360, nw, 28, '|< Start',
                                font=self.f_small, corner_radius=5)
        self.btn_prev  = Button(px+nw+3,     360, nw, 28, '< Prev',
                                font=self.f_small, corner_radius=5)
        self.btn_hnext = Button(px+2*(nw+3), 360, nw, 28, 'Next >',
                                font=self.f_small, corner_radius=5)
        self.btn_live  = Button(px+3*(nw+3), 360, nw, 28, 'Live >|',
                                font=self.f_small, corner_radius=5)

        # move log
        self.log_widget = ScrollLog(px, 378, PANEL_W - 10, WIN_H - 378 - 10,
                                    font=self.f_log)

        # action buttons (disambiguation) — built dynamically
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
    def _view_team(self) -> Team:
        """Which team's perspective to use for board orientation."""
        if self.game_mode == 'local':
            return self._live_state().active_player
        return self.player_color

    def _board_to_screen(self, row: int, col: int) -> Tuple[int, int]:
        """Top-left pixel of the cell for (row, col)."""
        if self._view_team() == Team.RED:
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
        if self._view_team() == Team.RED:
            return (7 - sr, sc)
        else:
            return (sr, 7 - sc)

    # ── game logic ───────────────────────────────────────────────────────────
    def new_game(self):
        """Start a fresh game (keeps the shared TT)."""
        # Stop ponder and any in-flight bot thread.
        self._stop_ponder()
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
        self._local_pass_pending = False
        self._metalic_bot._root = None   # discard stale tree; TT retains cross-game learning
        self._captures = {Team.RED: [], Team.BLUE: []}
        self._move_count    = 0
        self._next_chat_move = random.randint(3, 7)
        self.log_widget.lines.clear()
        self.log_widget.add('─── New game ───', C_YELLOW)
        self.log_widget.add(f'You play as {"RED" if self.player_color == Team.RED else "BLUE"}', C_WHITE)
        if self.game_mode == 'bot' and self._persona is None:
            self.log_widget.add(f'Bot budget: {self.sl_budget.value:.1f}s', C_DIM)
        if self.game_mode == 'bot':
            self.chat_widget.lines.clear()
            self._post_chat('idle')
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

    # ── Persona chat ─────────────────────────────────────────────────────────

    def _post_chat(self, event_type: str, color=None):
        """Post a character-voiced message to the chat widget (bot mode only)."""
        if self.game_mode != 'bot' or self._persona is None:
            return
        bank = PERSONA_CHAT.get(self._persona.name, {}).get(event_type, [])
        if not bank:
            bank = PERSONA_CHAT.get(self._persona.name, {}).get('idle', [])
        if not bank:
            return
        msg = random.choice(bank)
        pc  = PERSONA_COLORS.get(self._persona.name, C_WHITE)
        col = color or pc
        # Word-wrap the full line to fit the chat widget
        full_line = f'{self._persona.name}: {msg}'
        font = self.chat_widget.font
        max_w = self.chat_widget.rect.width - 16   # 6px left + 10px right margin
        words = full_line.split(' ')
        line_buf = ''
        for word in words:
            test = (line_buf + ' ' + word).lstrip()
            if font.size(test)[0] <= max_w:
                line_buf = test
            else:
                if line_buf:
                    self.chat_widget.add(line_buf, col)
                line_buf = word
        if line_buf:
            self.chat_widget.add(line_buf, col)

    def _on_move_chat(self, event_type: str, color=None):
        """Called after every move; also fires idle quips on schedule."""
        self._move_count += 1
        # Immediate event-driven message
        if event_type != 'idle':
            self._post_chat(event_type, color)
        # Scheduled idle quip
        if self._move_count >= self._next_chat_move:
            self._post_chat('idle')
            self._next_chat_move = self._move_count + random.randint(5, 10)

    # ── Tall grass exploration logging ───────────────────────────────────────

    def _log_exploration(self, old_state: GameState, new_state: GameState) -> None:
        """Log any newly explored tall grass squares and items found/dropped."""
        old_explored = old_state.tall_grass_explored
        new_explored  = new_state.tall_grass_explored
        newly = new_explored - old_explored
        if not newly:
            return
        old_floor = {(fi.row, fi.col): fi for fi in old_state.floor_items}
        new_floor = {(fi.row, fi.col): fi for fi in new_state.floor_items}
        for (r, c) in sorted(newly):
            # Check what was hidden at this square before exploration
            hidden = next((h for h in old_state.hidden_items if h.row == r and h.col == c), None)
            if hidden is None:
                self.log_widget.add(f'  [Grass ({r},{c})] nothing here', C_DIM)
            elif (r, c) in new_floor and (r, c) not in old_floor:
                # Item was dropped at this square (overflow — bag was full)
                self.log_widget.add(f'  [Grass ({r},{c})] {hidden.item.name} dropped (bag full)', C_GREEN)
            else:
                # Item was picked up directly
                self.log_widget.add(f'  [Grass ({r},{c})] found {hidden.item.name}!', C_GREEN)

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
        if self.game_mode == 'local':
            return False
        s = self._live_state()
        done, _ = is_terminal(s)
        return (not done) and (s.active_player != self.player_color)

    def _is_human_turn(self) -> bool:
        if self.game_mode == 'local':
            s = self._live_state()
            done, _ = is_terminal(s)
            return not done
        s = self._live_state()
        done, _ = is_terminal(s)
        return (not done) and (s.active_player == self.player_color)

    def _update_status(self):
        s  = self._live_state()
        done, winner = is_terminal(s)
        color_name = 'RED' if s.active_player == Team.RED else 'BLUE'
        if done:
            if self.game_mode == 'local':
                win_name = 'RED' if winner == Team.RED else ('BLUE' if winner else None)
                if win_name:
                    self.status_msg   = f'{win_name} wins!'
                    self.status_color = C_RED if winner == Team.RED else C_BLUE
                else:
                    self.status_msg   = 'Draw'
                    self.status_color = C_YELLOW
            elif winner == self.player_color:
                self.status_msg   = 'You win!'
                self.status_color = C_GREEN
            elif winner is None:
                self.status_msg   = 'Draw'
                self.status_color = C_YELLOW
            else:
                self.status_msg   = f'{self._bot_name} wins!'
                self.status_color = C_RED
        elif self.game_mode == 'local':
            if self._local_pass_pending:
                self.status_msg   = f'{color_name} — tap board to reveal'
                self.status_color = C_DIM
            else:
                self.status_msg   = f'{color_name}\'s turn  —  turn {s.turn_number}'
                self.status_color = C_RED if s.active_player == Team.RED else C_BLUE
        elif self._bot_running:
            self.status_msg   = f'{self._bot_name} thinking...  ({self.sl_budget.value:.1f}s)'
            self.status_color = C_CYAN
        elif self.hist_idx != -1:
            n = len(self.history)
            self.status_msg   = f'History view  [{self.hist_idx + 1}/{n}]'
            self.status_color = C_YELLOW
        elif s.active_player == self.player_color:
            self.status_msg   = f'Your turn ({color_name})  —  turn {s.turn_number}'
            self.status_color = C_WHITE
        else:
            self.status_msg   = f'Waiting for {self._bot_name} ({color_name})'
            self.status_color = C_DIM

    # ── bot thread ───────────────────────────────────────────────────────────
    def _stop_ponder(self) -> None:
        """Signal the ponder thread to stop and wait briefly for it to exit."""
        with self._bot_lock:
            self._ponder_running = False
        if self._ponder_thread and self._ponder_thread.is_alive():
            self._ponder_thread.join(timeout=0.2)
        self._ponder_thread = None

    def _start_ponder(self, state: GameState) -> None:
        """Begin background pondering on state (opponent's turn)."""
        self._stop_ponder()   # ensure no leftover thread
        with self._bot_lock:
            self._ponder_running = True

        def _run():
            try:
                self._metalic_bot.ponder(state, lambda: not self._ponder_running)
            except Exception:
                pass
            with self._bot_lock:
                self._ponder_running = False

        self._ponder_thread = threading.Thread(target=_run, daemon=True)
        self._ponder_thread.start()

    def _start_bot(self):
        if self._bot_running:
            return
        # Stop any background pondering first; the root was already advanced
        # through the human's move in _execute_move before this is called.
        self._stop_ponder()

        self._bot_running = True
        self._bot_result  = None
        if self._persona is not None:
            # Persona fixes the bot params — sliders are decorative in this mode
            self.shared_tt.access_pct = 1.0 if self._persona.use_transposition else 0.0
            self._metalic_bot.transposition = self.shared_tt
        else:
            # No persona — sliders control the bot
            self.shared_tt.access_pct = self.sl_tt.value
            self._metalic_bot.time_budget   = max(0.1, self.sl_budget.value)
            self._metalic_bot.transposition = self.shared_tt
        state = self._live_state()

        def _think():
            move = None
            try:
                move = self._metalic_bot.select_move(state)
            except Exception:
                import traceback
                traceback.print_exc()
                self.log_widget.add('Bot error — see terminal', C_ORANGE)
            with self._bot_lock:
                self._bot_result  = move
                self._bot_running = False

        t = threading.Thread(target=_think, daemon=True)
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
            # Determine chat event from board outcome
            _chat_event = 'idle'
            if is_stochastic:
                # Bot threw a pokeball
                if picked == 0:
                    self.log_widget.add(f'  >> Caught {t_name}!', C_GREEN)
                    _chat_event = 'capture'
                else:
                    self.log_widget.add(f'  >> {t_name} got away!', C_ORANGE)
                    self._miss_flash = (tr, tc, time.monotonic())
                    _chat_event = 'miss'
            elif move.action_type == ActionType.ATTACK and target is not None:
                _target_gone = new_state.board[tr][tc] is None
                _piece_gone  = new_state.board[pr][pc] is None
                if _target_gone and _piece_gone:
                    # Both disappeared: masterball caught something, OR bot piece walked into pokeball
                    if piece.piece_type in PAWN_TYPES:
                        _chat_event = 'capture'   # bot's pokeball/masterball caught target
                    else:
                        self.log_widget.add(f'  >> {p_name} was caught by {t_name}!', C_ORANGE)
                        _chat_event = 'miss'       # bot's pokemon walked into enemy pokeball
                elif _target_gone:
                    _chat_event = 'capture'    # bot killed/captured enemy; bot piece survived
                elif _piece_gone:
                    _chat_event = 'miss'       # bot's piece was removed (shouldn't happen in normal attack)
                # else: damage only → _chat_event stays 'idle'
            elif move.action_type == ActionType.EVOLVE:
                _chat_event = 'evolve'
            elif move.action_type == ActionType.FORESIGHT:
                _chat_event = 'foresight'
            self._on_move_chat(_chat_event)

        self.bot_move_highlight = (pr, pc, tr, tc)
        self._last_bot_move_time = time.monotonic()

        self._record_captures(s, new_state)
        self._log_exploration(s, new_state)
        self.history.append(new_state)
        self._update_status()

        done, _ = is_terminal(new_state)
        if not done:
            # Advance the persistent bot tree to the chosen move's child so
            # pondering (or the next select_move) reuses the explored subtree.
            bot = self._metalic_bot
            if bot._root is not None:
                bot._root = next(
                    (c for c in bot._root.children if c.move == move), None)
            if self._is_bot_turn():
                self._start_bot()
            else:
                # Human's turn — start pondering in the background
                self._start_ponder(new_state)
        else:
            _, winner = is_terminal(new_state)
            if winner != self.player_color:
                self._post_chat('win')
            else:
                self._post_chat('loss')
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
            # Determine chat event from board outcome (bot reacts to human's move)
            _chat_ev = 'idle'
            if is_stochastic:
                # Human threw a pokeball at a bot piece
                if picked == 0:
                    self.log_widget.add(f'  >> Caught {t_name}!', C_GREEN)
                    _chat_ev = 'miss'    # bot lost a piece — bot laments
                else:
                    self.log_widget.add(f'  >> {t_name} got away!', C_ORANGE)
                    self._miss_flash = (tr, tc, time.monotonic())
                    _chat_ev = 'idle'   # miss is neutral — bot says nothing meaningful
            elif move.action_type == ActionType.ATTACK and target is not None:
                _target_gone = new_state.board[tr][tc] is None
                _piece_gone  = new_state.board[pr][pc] is None
                if _target_gone and _piece_gone:
                    # Both disappeared: human pokeball caught bot piece, OR human piece walked into bot pokeball
                    if piece.piece_type in PAWN_TYPES:
                        _chat_ev = 'miss'    # human's pokeball caught a bot piece
                    else:
                        self.log_widget.add(f'  >> {p_name} was caught by {t_name}!', C_ORANGE)
                        _chat_ev = 'capture'  # human's pokemon was caught by bot's pokeball — bot gloats
                elif _target_gone:
                    _chat_ev = 'miss'     # human killed a bot piece; bot laments
                elif _piece_gone:
                    _chat_ev = 'capture'  # human piece removed (shouldn't normally happen)
                # else: damage only → _chat_ev stays 'idle'
            elif move.action_type == ActionType.EVOLVE:
                _chat_ev = 'evolve'
            elif move.action_type == ActionType.FORESIGHT:
                _chat_ev = 'foresight'
            self._on_move_chat(_chat_ev)

        self._record_captures(s, new_state)
        self._log_exploration(s, new_state)
        self.history.append(new_state)
        self.selected = None
        self.legal_for_sel = []
        self.pending_moves = []
        self.action_btns   = []

        done, winner = is_terminal(new_state)
        if done:
            if winner == self.player_color:
                self._post_chat('loss')   # player won → bot loses
            elif winner is not None:
                self._post_chat('win')
        if self.game_mode == 'local' and not done and self._pass_screen_on:
            self._local_pass_pending = True
        self._update_status()

        if not done and self._is_bot_turn():
            # Stop pondering, advance the persistent tree through this human move,
            # then let select_move reuse whatever the ponder thread explored.
            self._stop_ponder()
            bot = self._metalic_bot
            if bot._root is not None:
                bot._root = next(
                    (c for c in bot._root.children if c.move == move), None)
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
        # In local mode the "current player" is whoever's turn it is
        current_player = s.active_player if self.game_mode == 'local' else self.player_color

        # If disambiguation buttons are active, ignore board clicks
        if self.pending_moves:
            return

        piece = s.board[row][col]

        if self.selected is None:
            # Select own piece
            if piece and piece.team == current_player:
                self.selected = (row, col)
                all_legal = get_legal_moves(s)
                self.legal_for_sel = [m for m in all_legal
                                      if m.piece_row == row and m.piece_col == col]
                self.action_btns = []
        else:
            sr, sc = self.selected

            if (row, col) == (sr, sc):
                # Clicking the selected piece's own square:
                # show in-place actions (EVOLVE, PSYWAVE) before deselecting
                inplace_moves = [m for m in self.legal_for_sel
                                 if m.action_type in (ActionType.EVOLVE, ActionType.PSYWAVE)]
                if inplace_moves:
                    self.pending_moves = inplace_moves
                    self._build_action_buttons(inplace_moves)
                else:
                    # Deselect
                    self.selected = None
                    self.legal_for_sel = []
                    self.pending_moves = []
                    self.action_btns   = []
                return

            if piece and piece.team == current_player:
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
        by = 414   # below history nav (ends at y≈388) with room for header
        bh = 32
        pad = 4

        # Deduplicate: Quick Attack is keyed by (dest, attack-target);
        # overflow moves include overflow_keep so both options are preserved;
        # others by (type, slot)
        seen = set()
        unique: List[Move] = []
        for m in moves:
            if m.action_type == ActionType.QUICK_ATTACK:
                key = (m.action_type, m.target_row, m.target_col, m.secondary_row, m.secondary_col)
            elif m.overflow_keep is not None:
                key = (m.action_type, m.move_slot, m.overflow_keep)
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
                atk_target = s.board[m.target_row][m.target_col]
                t_name = PIECE_LABEL.get(atk_target.piece_type, '?') if atk_target else '?'
                lbl = f'QA: atk {t_name} → ({m.secondary_row},{m.secondary_col})'
            if m.overflow_keep == 'existing':
                piece_on_sq = s.board[m.piece_row][m.piece_col]
                existing_name = piece_on_sq.held_item.name if piece_on_sq else '?'
                lbl = f'Keep {existing_name} (drop new)'
            elif m.overflow_keep == 'new':
                lbl = 'Keep new item (drop old)'
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
    def run(self) -> Optional[str]:
        """Return 'menu' to go back to landing screen, None to quit."""
        while True:
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._stop_ponder()
                    self.shared_tt.save(TT_SAVE_PATH)
                    return None

                # Sliders
                self.sl_budget.handle(event)
                self.sl_tt.handle(event)

                # Log scroll
                self.log_widget.handle_scroll(event)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos

                    # Menu button — return to landing screen
                    if self.btn_menu.hit(event):
                        self._stop_ponder()
                        self.shared_tt.save(TT_SAVE_PATH)
                        return 'menu'

                    # Pass screen (local mode): any board click reveals next turn
                    if self._local_pass_pending:
                        rc = self._screen_to_board(pos[0], pos[1])
                        if rc is not None:
                            self._local_pass_pending = False
                            self._update_status()
                        continue

                    # Game mode toggle
                    if self.btn_vs_metalic.hit(event) and not self._bot_running:
                        # Always go back to the landing screen to pick a persona
                        self._stop_ponder()
                        self.shared_tt.save(TT_SAVE_PATH)
                        return 'menu'
                    if self.btn_local_mode.hit(event) and not self._bot_running:
                        self.game_mode = 'local'
                        self.btn_local_mode.active = True
                        self.btn_vs_metalic.active = False
                        self.new_game()
                        continue
                    if self.btn_pass_toggle.hit(event) and self.game_mode == 'local':
                        self._pass_screen_on = not self._pass_screen_on
                        self.btn_pass_toggle.active = self._pass_screen_on
                        # If screen was just disabled, clear any pending pass
                        if not self._pass_screen_on:
                            self._local_pass_pending = False
                        continue

                    # Color buttons — locked for forced-team personas
                    _forced = PERSONA_FORCED_PLAYER.get(
                        self._persona.name if self._persona else '')
                    if not _forced and not self._bot_running:
                        if self.btn_red.hit(event):
                            self.player_color = Team.RED
                            self.btn_red.active  = True
                            self.btn_blue.active = False
                            self.new_game()
                            continue
                        if self.btn_blue.hit(event):
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
        if self._local_pass_pending and self._pass_screen_on:
            self._draw_pass_screen(surf)
        self._draw_panel(surf, mouse_pos)

    def _draw_pass_screen(self, surf) -> None:
        """Covers the board with a dark overlay between local turns."""
        s = self._live_state()
        team = s.active_player
        color = C_RED if team == Team.RED else C_BLUE
        name  = 'RED' if team == Team.RED else 'BLUE'

        # Dark overlay over board area
        overlay = pygame.Surface((8 * CELL, 8 * CELL), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 220))
        surf.blit(overlay, (BOARD_X, BOARD_Y))

        # Centered text
        bx = BOARD_X + 4 * CELL
        by = BOARD_Y + 4 * CELL

        heading = self.f_title.render(f"{name}'s turn", True, color)
        sub     = self.f_body.render('Tap the board to reveal', True, C_DIM)
        surf.blit(heading, heading.get_rect(center=(bx, by - 18)))
        surf.blit(sub,     sub.get_rect(center=(bx, by + 14)))

    def _draw_title(self, surf):
        # Title bar
        pygame.draw.rect(surf, C_CARD, (0, 0, WIN_W, 56))
        pygame.draw.rect(surf, C_DIVIDER, (0, 55, WIN_W, 1))
        title = self.f_title.render('PokeChess', True, C_WHITE)
        surf.blit(title, (BOARD_X, 16))

        mouse_pos = pygame.mouse.get_pos()
        self.btn_menu.draw(surf, mouse_pos)

        # Status centered over the board area so it never clips into the right panel
        _board_cx = BOARD_X + 4 * CELL
        st = self.f_head.render(self.status_msg, True, self.status_color)
        st_rect = st.get_rect(center=(_board_cx, 28))
        surf.blit(st, st_rect)

        # Bot thinking spinner placed just right of the status text
        if self._bot_running:
            t = int(time.monotonic() * 3) % 4
            dots = '.' * (t + 1) + '   '
            sp = self.f_body.render(dots[:4], True, C_CYAN)
            surf.blit(sp, (st_rect.right + 4, 22))

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

        # Build floor-item lookup: (row, col) → FloorItem
        floor_item_map = {(fi.row, fi.col): fi for fi in state.floor_items}

        # Draw squares
        for r in range(8):
            for c in range(8):
                sx, sy = self._board_to_screen(r, c)
                is_light = (r + c) % 2 == 0
                base_col = LIGHT_SQ if is_light else DARK_SQ
                pygame.draw.rect(surf, base_col, (sx, sy, CELL, CELL))

                # Unexplored tall grass: dark overlay
                if r in TALL_GRASS_ROWS and (r, c) not in state.tall_grass_explored:
                    grass_ol = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                    grass_ol.fill((0, 0, 0, 230))
                    surf.blit(grass_ol, (sx, sy))

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

                # Floor item badge (drawn before piece so piece renders on top)
                fi = floor_item_map.get((r, c))
                if fi is not None and state.board[r][c] is None:
                    self._draw_floor_item(surf, fi.item, sx, sy)

                # Piece
                piece = state.board[r][c]
                if piece:
                    self._draw_piece(surf, piece, sx, sy, mouse_pos)

        # Board border
        brd = pygame.Rect(BOARD_X - 2, BOARD_Y - 2, 8 * CELL + 4, 8 * CELL + 4)
        pygame.draw.rect(surf, C_DIVIDER, brd, 2, border_radius=3)

        # Pokeball miss flash — "ESCAPED!" fades over the target square for 1.2s
        if self._miss_flash is not None:
            _mrow, _mcol, _mt = self._miss_flash
            _elapsed = time.monotonic() - _mt
            if _elapsed > 1.2:
                self._miss_flash = None
            else:
                _alpha = max(0, int(255 * (1.0 - _elapsed / 1.2)))
                _sx, _sy = self._board_to_screen(_mrow, _mcol)
                _esc_surf = self.f_head.render('ESCAPED!', True, C_ORANGE)
                _esc_surf.set_alpha(_alpha)
                surf.blit(_esc_surf, _esc_surf.get_rect(center=(_sx + CELL // 2, _sy + CELL // 2 - 4)))

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

        # Held item badge: small colored dot in bottom-right corner
        if piece.held_item != Item.NONE and piece.held_item in ITEM_DISPLAY:
            _, item_col = ITEM_DISPLAY[piece.held_item]
            badge_r = 6
            badge_cx = sx + CELL - badge_r - 3
            badge_cy = sy + CELL - badge_r - 10  # just above HP bar
            pygame.draw.circle(surf, (10, 10, 20), (badge_cx, badge_cy), badge_r + 1)
            pygame.draw.circle(surf, item_col, (badge_cx, badge_cy), badge_r)

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

    def _draw_floor_item(self, surf, item: Item, sx: int, sy: int) -> None:
        """Draw a small item badge centered in the square (sx, sy are top-left)."""
        lbl_str, color = ITEM_DISPLAY.get(item, ('??', C_WHITE))
        badge_w, badge_h = 30, 18
        bx = sx + (CELL - badge_w) // 2
        by = sy + (CELL - badge_h) // 2
        pygame.draw.rect(surf, (20, 20, 30), (bx - 1, by - 1, badge_w + 2, badge_h + 2),
                         border_radius=4)
        pygame.draw.rect(surf, color, (bx, by, badge_w, badge_h), border_radius=4)
        pygame.draw.rect(surf, (20, 20, 30), (bx, by, badge_w, badge_h), 1, border_radius=4)
        txt = self.f_small.render(lbl_str, True, (10, 10, 20))
        surf.blit(txt, txt.get_rect(center=(bx + badge_w // 2, by + badge_h // 2)))

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

        # ── Section: Game mode ────────────────────────────────────────────
        ml = self.f_head.render('Game mode:', True, C_DIM)
        surf.blit(ml, (px, 50))
        self.btn_vs_metalic.draw(surf, mouse_pos)
        self.btn_local_mode.draw(surf, mouse_pos)

        # ── Section: Color choice / pass-screen toggle ────────────────────
        pygame.draw.rect(surf, C_DIVIDER, (px, 100, bar_w, 1))
        if self.game_mode == 'local':
            self.btn_pass_toggle.draw(surf, mouse_pos)
        if self.game_mode == 'bot':
            forced = PERSONA_FORCED_PLAYER.get(
                self._persona.name if self._persona else '')
            if forced:
                lock_surf = self.f_body.render(
                    f'Team locked: you play {forced}', True, (220, 160, 40))
                surf.blit(lock_surf, (px, 106))
            else:
                lbl = self.f_head.render('You play as:', True, C_DIM)
                surf.blit(lbl, (px, 104))
                self.btn_red.draw(surf, mouse_pos)
                self.btn_blue.draw(surf, mouse_pos)

        # ── Section: Bot settings (bot mode only) ─────────────────────────
        pygame.draw.rect(surf, C_DIVIDER, (px, 178, PANEL_W - 10, 1))
        if self.game_mode == 'bot' and self._persona is not None:
            # Persona chat replaces knobs (name visible in each message)
            self.chat_widget.draw(surf, mouse_pos)
        elif self.game_mode == 'bot':
            # Fallback: show sliders if somehow no persona
            bl = self.f_head.render('Bot Settings', True, C_DIM)
            surf.blit(bl, (px, 184))
            self.sl_budget.draw(surf)
            self.sl_tt.draw(surf)

        # ── Section: Controls ─────────────────────────────────────────────
        pygame.draw.rect(surf, C_DIVIDER, (px, 310, PANEL_W - 10, 1))
        self.btn_new.draw(surf, mouse_pos)
        self.btn_undo.draw(surf, mouse_pos)

        # History nav
        n = len(self.history)
        cur_h = self.hist_idx if self.hist_idx != -1 else n - 1
        h_lbl = self.f_small.render(
            f'History: [{cur_h + 1}/{n}]',
            True, C_DIM)
        surf.blit(h_lbl, (px, 358))
        self.btn_hprev.draw(surf, mouse_pos)
        self.btn_prev.draw(surf, mouse_pos)
        self.btn_hnext.draw(surf, mouse_pos)
        self.btn_live.draw(surf, mouse_pos)

        # ── Section: Action / disambiguation OR selected info + log ──────
        pygame.draw.rect(surf, C_DIVIDER, (px, 392, PANEL_W - 10, 1))

        if self.pending_moves or self.action_btns:
            # Disambiguation panel takes over the lower half — log is hidden
            al = self.f_head.render('Choose action:', True, C_YELLOW)
            surf.blit(al, (px, 396))
            for btn in self.action_btns:
                btn.draw(surf, mouse_pos)
        else:
            # Selected piece info (if any)
            info_y = 396
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
            _banner_h = 64
            _banner_y = BOARD_Y + (8 * CELL - _banner_h) // 2
            _banner_surf = pygame.Surface((8 * CELL, _banner_h), pygame.SRCALPHA)
            _banner_surf.fill((10, 10, 20, 200))
            surf.blit(_banner_surf, (BOARD_X, _banner_y))
            _go_line1 = self.f_title.render(self.status_msg, True, self.status_color)
            _go_line2 = self.f_head.render('Press New Game to play again', True, C_YELLOW)
            _cx_board = BOARD_X + 4 * CELL
            surf.blit(_go_line1, _go_line1.get_rect(center=(_cx_board, _banner_y + 18)))
            surf.blit(_go_line2, _go_line2.get_rect(center=(_cx_board, _banner_y + 44)))


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
def main():
    # Centre the window on-screen before creating the display
    pygame.init()
    _si = pygame.display.Info()
    _wx = max(0, (_si.current_w - WIN_W) // 2)
    _wy = max(0, (_si.current_h - WIN_H) // 2)
    os.environ.setdefault('SDL_VIDEO_WINDOW_POS', f'{_wx},{_wy}')

    while True:
        cfg = LandingScreen().run()
        if cfg is None:
            # User closed the window on the landing screen
            break

        result = PokeChessApp(
            mode         = cfg['mode'],
            persona      = cfg.get('persona'),
            player_color = cfg.get('player_color', Team.RED),
        ).run()

        if result != 'menu':
            # User closed the window inside the game
            break

    pygame.quit()


if __name__ == '__main__':
    main()
