"""
Generate demo/board_preview.png for the README.
Run once: python demo/gen_board_preview.py
"""
import sys, os, urllib.request
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import GameState, PieceType, Team, PIECE_STATS

# ── Sprite loader ─────────────────────────────────────────────────────────────
SPRITE_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sprites')
SPRITE_SIZE = 88
os.makedirs(SPRITE_DIR, exist_ok=True)

_POKEMON_DEX = {
    PieceType.SQUIRTLE: 7, PieceType.CHARMANDER: 4, PieceType.BULBASAUR: 1,
    PieceType.MEW: 151, PieceType.PIKACHU: 25, PieceType.RAICHU: 26,
    PieceType.EEVEE: 133, PieceType.VAPOREON: 134, PieceType.FLAREON: 136,
    PieceType.LEAFEON: 470, PieceType.JOLTEON: 135, PieceType.ESPEON: 196,
    PieceType.POKEBALL: None, PieceType.MASTERBALL: None,
}
_cache = {}

def _fetch_sprite(pt):
    if pt in _cache:
        return _cache[pt]
    dex = _POKEMON_DEX.get(pt)
    if dex is None:
        img = np.zeros((SPRITE_SIZE, SPRITE_SIZE, 4), dtype=np.uint8)
        cx = cy = SPRITE_SIZE // 2; r = SPRITE_SIZE // 2 - 4
        for y in range(SPRITE_SIZE):
            for x in range(SPRITE_SIZE):
                if (x-cx)**2 + (y-cy)**2 <= r**2:
                    top = y < cy
                    if pt == PieceType.MASTERBALL:
                        img[y,x] = [130,50,220,255] if top else [240,240,240,255]
                    else:
                        img[y,x] = [220,50,50,255] if top else [240,240,240,255]
        _cache[pt] = img; return img
    path = os.path.join(SPRITE_DIR, f'{dex}.png')
    if not os.path.exists(path):
        url = f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{dex}.png'
        urllib.request.urlretrieve(url, path)
    raw = Image.open(path).convert('RGBA')
    alpha = np.array(raw)[:,:,3]
    rows_any = np.any(alpha > 10, axis=1); cols_any = np.any(alpha > 10, axis=0)
    if rows_any.any() and cols_any.any():
        rmin, rmax = np.where(rows_any)[0][[0,-1]]
        cmin, cmax = np.where(cols_any)[0][[0,-1]]
        raw = raw.crop((cmin, rmin, cmax+1, rmax+1))
    arr = np.array(raw.resize((SPRITE_SIZE, SPRITE_SIZE), Image.NEAREST))
    _cache[pt] = arr; return arr

# ── Renderer ──────────────────────────────────────────────────────────────────
CELL     = SPRITE_SIZE + 8
BOARD_PX = CELL * 8
_LIGHT   = np.array([240,217,181,255], dtype=np.uint8)
_DARK    = np.array([181,136, 99,255], dtype=np.uint8)
_RED_BDR = (220, 50, 50)
_BLU_BDR = ( 50,100,220)

def _render(state, ax, title='Starting Position'):
    canvas = np.zeros((BOARD_PX, BOARD_PX, 4), dtype=np.uint8)
    for r in range(8):
        for c in range(8):
            y0, x0 = (7-r)*CELL, c*CELL
            canvas[y0:y0+CELL, x0:x0+CELL] = _LIGHT if (r+c)%2==0 else _DARK
    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p is None: continue
            sp = _fetch_sprite(p.piece_type).astype(float)
            y0, x0 = (7-r)*CELL+4, c*CELL+4
            bg = canvas[y0:y0+SPRITE_SIZE, x0:x0+SPRITE_SIZE].astype(float)
            a  = sp[:,:,3:4] / 255.0
            canvas[y0:y0+SPRITE_SIZE, x0:x0+SPRITE_SIZE, :3] = np.clip(
                sp[:,:,:3]*a + bg[:,:,:3]*(1-a), 0, 255).astype(np.uint8)
            canvas[y0:y0+SPRITE_SIZE, x0:x0+SPRITE_SIZE, 3] = 255
    ax.imshow(canvas)
    totals, indices = {}, {}
    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p is None: continue
            key = (p.team, p.piece_type)
            totals[key] = totals.get(key,0)+1
            indices[(r,c)] = totals[key]
    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p is None: continue
            ec = [v/255 for v in (_RED_BDR if p.team==Team.RED else _BLU_BDR)]
            ax.add_patch(mpatches.FancyBboxPatch(
                (c*CELL+1,(7-r)*CELL+1), CELL-2, CELL-2,
                boxstyle='square,pad=0', lw=2.5, edgecolor=ec, facecolor='none'))
            key = (p.team, p.piece_type)
            if totals.get(key,1) > 1:
                ax.text(c*CELL+CELL-4,(7-r)*CELL+12, str(indices[(r,c)]),
                        fontsize=7, fontweight='bold', color=ec, ha='right', va='top')
            if p.piece_type == PieceType.MASTERBALL:
                ax.text(c*CELL+CELL//2, (7-r)*CELL+int(CELL*0.36), 'M',
                        fontsize=int(CELL*0.28), fontweight='bold',
                        color='black', ha='center', va='center')
    ax.set_xticks([c*CELL+CELL//2 for c in range(8)])
    ax.set_yticks([(7-r)*CELL+CELL//2 for r in range(8)])
    ax.set_xticklabels(range(8), fontsize=9)
    ax.set_yticklabels(range(8), fontsize=9)
    ax.tick_params(length=0)
    ax.set_xlim(0, BOARD_PX); ax.set_ylim(BOARD_PX, 0)
    ax.set_title(title, fontsize=15, pad=10)

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Fetching sprites…')
    for pt in PieceType:
        _fetch_sprite(pt)
    print('Rendering starting position…')
    fig, ax = plt.subplots(figsize=(9, 9))
    _render(GameState.new_game(), ax)
    plt.tight_layout()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'board_preview.png')
    fig.savefig(out, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {out}')
