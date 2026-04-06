"""
Generate demo/board_preview.png for the README.
Run once: python demo/gen_board_preview.py

Matches the pokechess_ui.py visual style:
- Pokemon pieces drawn as circular chips (team-colour ring, dark inner circle, sprite)
- Pokeballs drawn as proper pokeball icons (top/bottom halves, dividing line, centre button)
"""
import sys, os, urllib.request
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import GameState, PieceType, Team, PIECE_STATS

# ── Layout constants (mirror ui proportions) ──────────────────────────────────
SPRITE_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sprites')
CELL        = 96       # pixels per board cell
RING_R      = 38       # outer ring radius (px)
RING_BORDER = 6        # ring thickness (px)
INNER_R     = RING_R - RING_BORDER   # = 32  inner circle radius (pokemon sprite area)
BALL_R      = RING_R - 4             # = 34  pokeball radius (same ratio as UI)
BTN_R       = 7                      # pokeball centre-button radius
SPRITE_PX   = INNER_R * 2           # = 64  pokemon sprite diameter
BOARD_PX    = CELL * 8

os.makedirs(SPRITE_DIR, exist_ok=True)

_POKEMON_DEX = {
    PieceType.SQUIRTLE:        7,
    PieceType.CHARMANDER:      4,
    PieceType.BULBASAUR:       1,
    PieceType.MEW:           151,
    PieceType.PIKACHU:        25,
    PieceType.RAICHU:         26,
    PieceType.EEVEE:         133,
    PieceType.VAPOREON:      134,
    PieceType.FLAREON:       136,
    PieceType.LEAFEON:       470,
    PieceType.JOLTEON:       135,
    PieceType.ESPEON:        196,
    PieceType.POKEBALL:     None,
    PieceType.MASTERBALL:   None,
    PieceType.SAFETYBALL:   None,
    PieceType.MASTER_SAFETYBALL: None,
}

# Precompute coordinate grids for CELL×CELL operations
_CY, _CX = np.mgrid[0:CELL, 0:CELL]
_CC = CELL // 2
_DIST = np.sqrt((_CX - _CC) ** 2 + (_CY - _CC) ** 2)

# ── Palette ───────────────────────────────────────────────────────────────────
_LIGHT_SQ  = np.array([240, 217, 181, 255], dtype=np.uint8)
_DARK_SQ   = np.array([181, 136,  99, 255], dtype=np.uint8)
_BG_INNER  = np.array([ 18,  20,  30, 255], dtype=np.uint8)   # UI BG colour
_RED_RGBA  = np.array([220,  50,  50, 255], dtype=np.uint8)
_BLUE_RGBA = np.array([ 50, 100, 220, 255], dtype=np.uint8)

# ── Sprite caches ─────────────────────────────────────────────────────────────
_pokemon_cache: dict = {}   # PieceType → SPRITE_PX×SPRITE_PX RGBA, circle-clipped
_ball_cache:    dict = {}   # PieceType → CELL×CELL RGBA (transparent outside BALL_R)


def _alpha_over(dst: np.ndarray, src: np.ndarray) -> None:
    """Alpha-composite src over dst in-place.  Both H×W×4 uint8."""
    a  = src[:, :, 3:4].astype(float) / 255.0
    bg = dst[:, :, :3].astype(float)
    fg = src[:, :, :3].astype(float)
    dst[:, :, :3] = np.clip(fg * a + bg * (1.0 - a), 0, 255).astype(np.uint8)
    dst[:, :, 3]  = np.maximum(dst[:, :, 3], src[:, :, 3])


def _load_pokemon_sprite(pt: PieceType) -> np.ndarray:
    """Return SPRITE_PX×SPRITE_PX RGBA, cropped tight and circle-clipped."""
    if pt in _pokemon_cache:
        return _pokemon_cache[pt]
    dex = _POKEMON_DEX.get(pt)
    if dex is None:
        arr = np.zeros((SPRITE_PX, SPRITE_PX, 4), dtype=np.uint8)
        _pokemon_cache[pt] = arr
        return arr
    path = os.path.join(SPRITE_DIR, f'{dex}.png')
    if not os.path.exists(path):
        url = (f'https://raw.githubusercontent.com/PokeAPI/sprites/master'
               f'/sprites/pokemon/{dex}.png')
        urllib.request.urlretrieve(url, path)
    raw   = Image.open(path).convert('RGBA')
    alpha = np.array(raw)[:, :, 3]
    rows  = np.any(alpha > 10, axis=1)
    cols  = np.any(alpha > 10, axis=0)
    if rows.any() and cols.any():
        r0, r1 = np.where(rows)[0][[0, -1]]
        c0, c1 = np.where(cols)[0][[0, -1]]
        raw = raw.crop((c0, r0, c1 + 1, r1 + 1))
    arr = np.array(raw.resize((SPRITE_PX, SPRITE_PX), Image.NEAREST))
    # Clip to circle so it stays inside the inner ring
    sy, sx = np.mgrid[0:SPRITE_PX, 0:SPRITE_PX]
    mid    = SPRITE_PX // 2
    arr[np.sqrt((sx - mid) ** 2 + (sy - mid) ** 2) > INNER_R, 3] = 0
    _pokemon_cache[pt] = arr
    return arr


def _make_ball_cell(pt: PieceType) -> np.ndarray:
    """Return CELL×CELL RGBA pokeball image (transparent outside BALL_R).

    Matches pokechess_ui.py _draw_ball():
      - top half in red/purple, bottom half in white/black
      - outer border circle, horizontal dividing line, centre button
    """
    if pt in _ball_cache:
        return _ball_cache[pt]

    buf       = np.zeros((CELL, CELL, 4), dtype=np.uint8)
    is_master = pt in (PieceType.MASTERBALL, PieceType.MASTER_SAFETYBALL)
    is_safety = pt in (PieceType.SAFETYBALL, PieceType.MASTER_SAFETYBALL)
    top_col   = np.array([128,   0, 180, 255]) if is_master else np.array([200,  50,  50, 255])
    bot_col   = np.array([240, 240, 240, 255]) if is_safety  else np.array([ 30,  30,  30, 255])
    line_col  = np.array([ 20,  20,  20, 255])

    dist = _DIST
    mask_ball  = dist <= BALL_R
    mask_top   = (_CY < _CC) & mask_ball
    mask_bot   = (_CY >= _CC) & mask_ball
    mask_btn   = dist <= BTN_R
    mask_bdr   = (dist >= BALL_R - 1.5) & (dist <= BALL_R + 0.5)
    mask_btn_b = (dist >= BTN_R  - 1.5) & (dist <= BTN_R  + 0.5) & mask_ball

    buf[mask_top] = top_col
    buf[mask_bot] = bot_col
    buf[mask_ball & mask_btn] = bot_col   # centre button fill
    buf[mask_ball, 3] = 255              # opaque inside ball
    buf[mask_bdr]     = line_col         # outer border
    buf[mask_btn_b]   = line_col         # button border
    # Horizontal dividing line
    x0, x1 = max(0, _CC - BALL_R), min(CELL, _CC + BALL_R + 1)
    buf[_CC, x0:x1]    = line_col
    buf[_CC, x0:x1, 3] = 255

    # Master-ball 'M' label
    if is_master:
        from PIL import ImageDraw, ImageFont
        pil  = Image.fromarray(buf, 'RGBA')
        draw = ImageDraw.Draw(pil)
        fsz  = max(8, BALL_R // 2)
        font = None
        for fpath in ('/System/Library/Fonts/Arial.ttf', '/Library/Fonts/Arial.ttf',
                      '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf'):
            try:
                font = ImageFont.truetype(fpath, fsz); break
            except Exception:
                pass
        if font is None:
            font = ImageFont.load_default()
        draw.text((_CC, _CC - BALL_R // 2), 'M',
                  fill=(240, 240, 255, 255), font=font, anchor='mm')
        buf = np.array(pil)

    _ball_cache[pt] = buf
    return buf


def _render_piece_cell(p) -> np.ndarray:
    """Return CELL×CELL RGBA for piece p — ring + sprite/ball, matching UI style."""
    buf       = np.zeros((CELL, CELL, 4), dtype=np.uint8)
    team_rgba = _RED_RGBA if p.team == Team.RED else _BLUE_RGBA
    is_ball   = p.piece_type in (PieceType.POKEBALL, PieceType.MASTERBALL,
                                  PieceType.SAFETYBALL, PieceType.MASTER_SAFETYBALL)

    # 1. Team-colour ring
    buf[_DIST <= RING_R] = team_rgba

    if is_ball:
        # 2a. Composite pokeball (transparent outside BALL_R, so ring shows at edges)
        _alpha_over(buf, _make_ball_cell(p.piece_type))
    else:
        # 2b. Dark inner circle (UI BG colour)
        buf[_DIST <= INNER_R] = _BG_INNER
        # 3. Composite pokemon sprite (already circle-clipped to INNER_R)
        sp     = _load_pokemon_sprite(p.piece_type)
        off    = (CELL - SPRITE_PX) // 2
        region = buf[off:off + SPRITE_PX, off:off + SPRITE_PX]
        _alpha_over(region, sp)

    return buf


# ── Board renderer ─────────────────────────────────────────────────────────────

def _render(state, ax, title='Starting Position'):
    canvas = np.zeros((BOARD_PX, BOARD_PX, 4), dtype=np.uint8)

    # Checkered board
    for r in range(8):
        for c in range(8):
            y0 = (7 - r) * CELL
            x0 = c * CELL
            canvas[y0:y0 + CELL, x0:x0 + CELL] = (
                _LIGHT_SQ if (r + c) % 2 == 0 else _DARK_SQ
            )

    # Count duplicates for index labels
    totals: dict = {}
    indices: dict = {}
    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p is None:
                continue
            key = (p.team, p.piece_type)
            totals[key] = totals.get(key, 0) + 1
            indices[(r, c)] = totals[key]

    # Draw pieces
    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p is None:
                continue
            y0 = (7 - r) * CELL
            x0 = c * CELL
            _alpha_over(canvas[y0:y0 + CELL, x0:x0 + CELL], _render_piece_cell(p))

    ax.imshow(canvas)

    # Overlay text annotations
    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p is None:
                continue
            ec  = [v / 255 for v in (_RED_RGBA[:3] if p.team == Team.RED else _BLUE_RGBA[:3])]
            key = (p.team, p.piece_type)
            if totals.get(key, 1) > 1:
                ax.text(c * CELL + CELL - 4, (7 - r) * CELL + 12,
                        str(indices[(r, c)]),
                        fontsize=7, fontweight='bold', color=ec, ha='right', va='top')
            if p.piece_type in (PieceType.MASTERBALL, PieceType.MASTER_SAFETYBALL):
                ax.text(c * CELL + CELL // 2, (7 - r) * CELL + int(CELL * 0.36), 'M',
                        fontsize=int(CELL * 0.28), fontweight='bold',
                        color='white', ha='center', va='center')

    ax.set_xticks([c * CELL + CELL // 2 for c in range(8)])
    ax.set_yticks([(7 - r) * CELL + CELL // 2 for r in range(8)])
    ax.set_xticklabels(range(8), fontsize=9)
    ax.set_yticklabels(range(8), fontsize=9)
    ax.tick_params(length=0)
    ax.set_xlim(0, BOARD_PX)
    ax.set_ylim(BOARD_PX, 0)
    ax.set_title(title, fontsize=15, pad=10)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Fetching sprites…')
    for pt, dex in _POKEMON_DEX.items():
        if dex is not None:
            _load_pokemon_sprite(pt)
    print('Rendering starting position…')
    fig, ax = plt.subplots(figsize=(9, 9))
    _render(GameState.new_game(), ax)
    plt.tight_layout()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'board_preview.png')
    fig.savefig(out, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {out}')
