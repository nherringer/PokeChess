/*
 * PokeChess C++ engine — rollout hot-loop port.
 *
 * Exposed to Python via pybind11:
 *   run_rollouts(state_bytes, n, depth, seed)         -> int (RED win count)
 *   run_rollouts_detailed(state_bytes, n, depth, seed) -> (red, blue, draws)
 *   run_rollout_with_rolls(state_bytes, rolls, depth)  -> int (1=RED, 0=BLUE/draw)
 *
 * Wire format produced by cpp/state_codec.py — see decode_state() for layout.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <cstdint>
#include <cstring>
#include <algorithm>
namespace py = pybind11;

// ---------------------------------------------------------------------------
// Enum constants (values match Python auto()-generated, starting at 1)
// ---------------------------------------------------------------------------

// PieceType
static constexpr uint8_t PT_NONE              = 0;
static constexpr uint8_t PT_SQUIRTLE          = 1;
static constexpr uint8_t PT_CHARMANDER        = 2;
static constexpr uint8_t PT_BULBASAUR         = 3;
static constexpr uint8_t PT_MEW               = 4;
static constexpr uint8_t PT_POKEBALL          = 5;
static constexpr uint8_t PT_MASTERBALL        = 6;
static constexpr uint8_t PT_SAFETYBALL        = 7;
static constexpr uint8_t PT_MASTER_SAFETYBALL = 8;
static constexpr uint8_t PT_PIKACHU           = 9;
static constexpr uint8_t PT_RAICHU            = 10;
static constexpr uint8_t PT_EEVEE             = 11;
static constexpr uint8_t PT_VAPOREON          = 12;
static constexpr uint8_t PT_FLAREON           = 13;
static constexpr uint8_t PT_LEAFEON           = 14;
static constexpr uint8_t PT_JOLTEON           = 15;
static constexpr uint8_t PT_ESPEON            = 16;

// Team
static constexpr uint8_t TEAM_RED  = 1;
static constexpr uint8_t TEAM_BLUE = 2;

// Item
static constexpr uint8_t ITEM_NONE         = 1;
static constexpr uint8_t ITEM_WATERSTONE   = 2;
static constexpr uint8_t ITEM_FIRESTONE    = 3;
static constexpr uint8_t ITEM_LEAFSTONE    = 4;
static constexpr uint8_t ITEM_THUNDERSTONE = 5;
static constexpr uint8_t ITEM_BENTSPOON    = 6;

// PokemonType
static constexpr uint8_t PTYPE_WATER    = 1;
static constexpr uint8_t PTYPE_FIRE     = 2;
static constexpr uint8_t PTYPE_GRASS    = 3;
static constexpr uint8_t PTYPE_PSYCHIC  = 4;
static constexpr uint8_t PTYPE_ELECTRIC = 5;
static constexpr uint8_t PTYPE_NORMAL   = 6;
static constexpr uint8_t PTYPE_NONE_T   = 7;

// ActionType
static constexpr uint8_t ACT_MOVE         = 1;
static constexpr uint8_t ACT_ATTACK       = 2;
static constexpr uint8_t ACT_FORESIGHT    = 3;
static constexpr uint8_t ACT_TRADE        = 4;
static constexpr uint8_t ACT_EVOLVE       = 5;
static constexpr uint8_t ACT_QUICK_ATTACK = 6;
static constexpr uint8_t ACT_RELEASE      = 7;
static constexpr uint8_t ACT_PSYWAVE      = 8;

// Result codes
static constexpr int WIN_NONE = 0;
static constexpr int WIN_RED  = 1;
static constexpr int WIN_BLUE = 2;
static constexpr int WIN_DRAW = 3;

// ---------------------------------------------------------------------------
// Static data tables (index = piece type 0..16)
// ---------------------------------------------------------------------------

static const uint8_t POKE_TYPE[17] = {
    0,
    PTYPE_WATER, PTYPE_FIRE, PTYPE_GRASS, PTYPE_PSYCHIC,    // 1-4
    PTYPE_NONE_T, PTYPE_NONE_T, PTYPE_NONE_T, PTYPE_NONE_T, // 5-8
    PTYPE_ELECTRIC, PTYPE_ELECTRIC,                          // 9-10
    PTYPE_NORMAL,                                            // 11
    PTYPE_WATER, PTYPE_FIRE, PTYPE_GRASS, PTYPE_ELECTRIC, PTYPE_PSYCHIC, // 12-16
};

static const int16_t MAX_HP[17] = {
    0,
    200, 200, 200, 250,  // 1-4
    0, 0, 0, 0,          // 5-8
    200, 250,            // 9-10 Pikachu, Raichu
    150,                 // 11 Eevee
    300, 220, 220, 200, 220, // 12-16 Vaporeon/Flareon/Leafeon/Jolteon/Espeon
};

static const int16_t BASE_DAMAGE[17] = {
    0,
    100, 100, 100, 100,  // 1-4 (Mew per-slot handled separately)
    0, 0, 0, 0,          // 5-8
    100, 100,            // 9-10
    50,                  // 11 Eevee
    100, 180, 100, 100, 80, // 12-16 (Flareon=180, Espeon=80)
};

static inline uint8_t eevee_evo(uint8_t item) {
    switch (item) {
        case ITEM_WATERSTONE:   return PT_VAPOREON;
        case ITEM_FIRESTONE:    return PT_FLAREON;
        case ITEM_LEAFSTONE:    return PT_LEAFEON;
        case ITEM_THUNDERSTONE: return PT_JOLTEON;
        case ITEM_BENTSPOON:    return PT_ESPEON;
        default:                return PT_NONE;
    }
}

// Mew slot → attack PokemonType: slot 0=Fire, 1=Water, 2=Grass
static const uint8_t MEW_SLOT_TYPE[3] = {PTYPE_FIRE, PTYPE_WATER, PTYPE_GRASS};

// MATCHUP_INT[atk][def]: 5=0.5x, 10=1x, 20=2x (multiply result by 10 = actual damage)
// Indices 1-7; [0] unused.
static const int16_t MATCHUP_INT[8][8] = {
    {0,  0,  0,  0,  0,  0,  0,  0},  // [0] unused
    {0,  5, 20,  5, 10, 10, 10, 10},  // [1] WATER  (beats FIRE)
    {0,  5,  5, 20, 10, 10, 10, 10},  // [2] FIRE   (beats GRASS)
    {0, 20,  5,  5, 10, 10, 10, 10},  // [3] GRASS  (beats WATER)
    {0, 10, 10, 10, 10, 10, 10, 10},  // [4] PSYCHIC
    {0, 20, 10, 10, 10, 10, 10, 10},  // [5] ELECTRIC (beats WATER)
    {0, 10, 10, 10, 10, 10, 10, 10},  // [6] NORMAL
    {0, 10, 10, 10, 10, 10, 10, 10},  // [7] NONE
};

// ---------------------------------------------------------------------------
// Predicates
// ---------------------------------------------------------------------------

static inline bool is_pawn(uint8_t pt) {
    return pt >= PT_POKEBALL && pt <= PT_MASTER_SAFETYBALL;
}
static inline bool is_king(uint8_t pt) {
    return pt == PT_PIKACHU || pt == PT_RAICHU || (pt >= PT_EEVEE && pt <= PT_ESPEON);
}
static inline bool is_safetyball(uint8_t pt) {
    return pt == PT_SAFETYBALL || pt == PT_MASTER_SAFETYBALL;
}
static inline bool in_bounds(int r, int c) {
    return (unsigned)r < 8 && (unsigned)c < 8;
}
static inline uint8_t other_team(uint8_t t) {
    return t == TEAM_RED ? TEAM_BLUE : TEAM_RED;
}
static inline int ti(uint8_t team) { return team == TEAM_RED ? 0 : 1; }
static inline int fwd(uint8_t team) { return team == TEAM_RED ? 1 : -1; }

// ---------------------------------------------------------------------------
// Damage calculation — matches Python rules.py (with banker's rounding)
// ---------------------------------------------------------------------------

static int calc_damage(uint8_t atk_pt, uint8_t def_pt, int slot) {
    int base;
    int atk_ptype;
    if (atk_pt == PT_MEW) {
        base = 100;
        atk_ptype = (slot >= 0 && slot < 3) ? MEW_SLOT_TYPE[slot] : PTYPE_FIRE;
    } else {
        base = BASE_DAMAGE[atk_pt];
        atk_ptype = POKE_TYPE[atk_pt];
    }
    if (def_pt == PT_LEAFEON) base = base - 40 < 1 ? 1 : base - 40;
    int def_ptype = POKE_TYPE[def_pt];
    int m = MATCHUP_INT[atk_ptype][def_ptype]; // 5, 10, or 20
    // raw = base * (m/10). We want round(raw / 10) * 10 with banker's rounding.
    // raw100 = base * m;  round(raw100/100) with banker's, then * 10.
    int raw100 = base * m;
    int q = raw100 / 100;
    int r = raw100 % 100;
    int dmg;
    if (r < 50)       dmg = q * 10;
    else if (r > 50)  dmg = (q + 1) * 10;
    else              dmg = (q % 2 == 0) ? q * 10 : (q + 1) * 10; // banker's
    return dmg < 10 ? 10 : dmg;
}

// ---------------------------------------------------------------------------
// Data structures
// ---------------------------------------------------------------------------

struct StoredPiece {
    uint8_t type = PT_NONE;
    uint8_t team = 0;
    uint8_t item = ITEM_NONE;
    int16_t hp   = 0;
};

struct Piece {
    uint8_t  type = PT_NONE;
    uint8_t  team = 0;
    uint8_t  row  = 0;
    uint8_t  col  = 0;
    int16_t  hp   = 0;
    uint8_t  item = ITEM_NONE;
    StoredPiece stored{};
};

struct Foresight {
    bool     active           = false;
    uint8_t  row              = 0;
    uint8_t  col              = 0;
    int16_t  damage           = 0;
    uint16_t resolves_on_turn = 0;
};

// board[r][c] = index into pieces[]; -1 = empty.
struct State {
    int8_t   board[8][8];
    Piece    pieces[32];
    int      n_pieces  = 0;
    uint8_t  active    = TEAM_RED;
    uint16_t turn      = 1;
    uint8_t  has_traded[2] = {0, 0};  // [0]=RED [1]=BLUE
    uint8_t  fs_used[2]    = {0, 0};
    Foresight foresight[2];           // [0]=RED [1]=BLUE

    State() { std::memset(board, -1, sizeof(board)); }
};

// ---------------------------------------------------------------------------
// Wire format decoder (matches cpp/state_codec.py)
//
// Header  7 bytes: active(B) turn(H) traded_red(B) traded_blue(B)
//                  fs_used_red(B) fs_used_blue(B)
// Foresight×2 14 bytes: [active(B) row(B) col(B) damage(h) resolves(H)] ×2
// n_pieces  1 byte
// Per piece 14 bytes: type(B) team(B) row(B) col(B) hp(h) item(B)
//                     has_stored(B) stored_type(B) stored_team(B) stored_hp(h)
//                     stored_item(B) _pad(x)
// ---------------------------------------------------------------------------

static State decode_state(const void* raw, int /*len*/) {
    State s;
    const uint8_t* p = static_cast<const uint8_t*>(raw);

    s.active         = p[0];
    s.turn           = (uint16_t)(p[1] | (p[2] << 8));
    s.has_traded[0]  = p[3];
    s.has_traded[1]  = p[4];
    s.fs_used[0]     = p[5];
    s.fs_used[1]     = p[6];
    p += 7;

    for (int i = 0; i < 2; i++) {
        s.foresight[i].active           = p[0] != 0;
        s.foresight[i].row              = p[1];
        s.foresight[i].col              = p[2];
        s.foresight[i].damage           = (int16_t)(p[3] | (p[4] << 8));
        s.foresight[i].resolves_on_turn = (uint16_t)(p[5] | (p[6] << 8));
        p += 7;
    }

    s.n_pieces = (int)(*p++);
    for (int i = 0; i < s.n_pieces; i++) {
        Piece& pc = s.pieces[i];
        pc.type = p[0];
        pc.team = p[1];
        pc.row  = p[2];
        pc.col  = p[3];
        pc.hp   = (int16_t)(p[4] | (p[5] << 8));
        pc.item = p[6];
        if (p[7]) { // has_stored
            pc.stored.type = p[8];
            pc.stored.team = p[9];
            pc.stored.hp   = (int16_t)(p[10] | (p[11] << 8));
            pc.stored.item = p[12];
        }
        p += 14;
        s.board[pc.row][pc.col] = (int8_t)i;
    }
    return s;
}

// ---------------------------------------------------------------------------
// Board helpers
// ---------------------------------------------------------------------------

static inline Piece* piece_at(State& s, int r, int c) {
    int8_t idx = s.board[r][c];
    return idx < 0 ? nullptr : &s.pieces[idx];
}

static inline int8_t idx_at(const State& s, int r, int c) {
    return s.board[r][c];
}

static int count_team(const State& s, uint8_t team) {
    int cnt = 0;
    for (int i = 0; i < s.n_pieces; i++)
        if (s.pieces[i].type != PT_NONE && s.pieces[i].team == team) cnt++;
    return cnt;
}

// Find a free slot in pieces[] != skip_idx.
static int alloc_slot(State& s, int skip_idx = -1) {
    for (int i = 0; i < 32; i++) {
        if (i == skip_idx) continue;
        if (s.pieces[i].type == PT_NONE) {
            if (i >= s.n_pieces) s.n_pieces = i + 1;
            return i;
        }
    }
    return -1;
}

// ---------------------------------------------------------------------------
// Move struct
// ---------------------------------------------------------------------------

struct Move {
    uint8_t pr, pc;
    uint8_t action;
    uint8_t tr, tc;
    uint8_t sr, sc;  // secondary destination (QUICK_ATTACK)
    int8_t  slot;    // Mew attack slot (0-2) or Eevee evolve slot (0-4); -1 otherwise
};

// ---------------------------------------------------------------------------
// Foresight resolution — called at the start of each turn
// ---------------------------------------------------------------------------

static void resolve_foresight(State& s) {
    int idx = ti(s.active);
    Foresight& fx = s.foresight[idx];
    if (!fx.active || fx.resolves_on_turn != s.turn) return;
    int8_t tidx = idx_at(s, fx.row, fx.col);
    if (tidx >= 0) {
        Piece& t = s.pieces[tidx];
        if (!is_pawn(t.type)) {
            t.hp -= fx.damage;
            if (t.hp <= 0) {
                s.board[fx.row][fx.col] = -1;
                t.type = PT_NONE;
            }
        }
    }
    fx.active = false;
}

// ---------------------------------------------------------------------------
// Move generation helpers
// ---------------------------------------------------------------------------

static void add_mv(Move* mv, int& n,
                   uint8_t pr, uint8_t pc, uint8_t action,
                   uint8_t tr, uint8_t tc,
                   uint8_t sr = 0, uint8_t sc_ = 0, int8_t slot = -1) {
    mv[n++] = {pr, pc, action, tr, tc, sr, sc_, slot};
}

// Safetyball step — can move onto injured ally.
static void step_sb(State& s, Piece& p, Move* mv, int& n, int dr, int dc, int steps) {
    for (int i = 0, r = p.row + dr, c = p.col + dc;
         i < steps && in_bounds(r, c);
         i++, r += dr, c += dc)
    {
        int8_t oidx = idx_at(s, r, c);
        if (oidx < 0) {
            add_mv(mv, n, p.row, p.col, ACT_MOVE, r, c);
        } else {
            Piece& occ = s.pieces[oidx];
            if (occ.team == p.team) {
                if (p.stored.type == PT_NONE &&
                    MAX_HP[occ.type] > 0 &&
                    occ.hp < MAX_HP[occ.type] &&
                    occ.type != PT_PIKACHU &&
                    count_team(s, p.team) >= 3)
                {
                    add_mv(mv, n, p.row, p.col, ACT_MOVE, r, c);
                }
            }
            break;
        }
    }
}

// Jump (knight-style) — leaps over pieces.
template<int N>
static void jumps(State& s, Piece& p, Move* mv, int& n, const int deltas[N][2]) {
    for (int i = 0; i < N; i++) {
        int r = p.row + deltas[i][0], c = p.col + deltas[i][1];
        if (!in_bounds(r, c)) continue;
        int8_t oidx = idx_at(s, r, c);
        if (oidx < 0) {
            add_mv(mv, n, p.row, p.col, ACT_MOVE, r, c);
        } else {
            Piece& occ = s.pieces[oidx];
            if (occ.team != p.team && !is_safetyball(occ.type))
                add_mv(mv, n, p.row, p.col, ACT_ATTACK, r, c);
        }
    }
}

static void king_sq(State& s, Piece& p, Move* mv, int& n) {
    static const int K[8][2] = {
        {-1,-1},{-1,0},{-1,1},{0,-1},{0,1},{1,-1},{1,0},{1,1}
    };
    jumps<8>(s, p, mv, n, K);
}

static void trades(State& s, Piece& p, Move* mv, int& n) {
    if (s.has_traded[ti(p.team)]) return;
    for (int dr = -1; dr <= 1; dr++) for (int dc = -1; dc <= 1; dc++) {
        if (!dr && !dc) continue;
        int r = p.row + dr, c = p.col + dc;
        if (!in_bounds(r, c)) continue;
        Piece* nb = piece_at(s, r, c);
        if (nb && nb->team == p.team && !is_pawn(nb->type) && nb->item != p.item)
            add_mv(mv, n, p.row, p.col, ACT_TRADE, r, c);
    }
}

static void raichu_cardinals(State& s, Piece& p, Move* mv, int& n) {
    // Unobstructed 2-square cardinal jumps — intermediate square is leaped over.
    static const int D[4][2] = {{2,0},{-2,0},{0,2},{0,-2}};
    for (auto& d : D) {
        int dr = p.row + d[0], dc = p.col + d[1];
        if (!in_bounds(dr, dc)) continue;
        int8_t oidx = idx_at(s, dr, dc);
        if (oidx < 0) add_mv(mv, n, p.row, p.col, ACT_MOVE, dr, dc);
        else {
            Piece& occ = s.pieces[oidx];
            if (occ.team != p.team && !is_safetyball(occ.type))
                add_mv(mv, n, p.row, p.col, ACT_ATTACK, dr, dc);
        }
    }
}

// Stealball cannot target pawns or Pikachu.
static void pawn_step(State& s, Piece& p, Move* mv, int& n, int dr, int dc, int steps) {
    for (int i = 0, r = p.row + dr, c = p.col + dc;
         i < steps && in_bounds(r, c);
         i++, r += dr, c += dc)
    {
        int8_t oidx = idx_at(s, r, c);
        if (oidx < 0) {
            add_mv(mv, n, p.row, p.col, ACT_MOVE, r, c);
        } else {
            Piece& occ = s.pieces[oidx];
            if (occ.team != p.team && !is_safetyball(occ.type) &&
                !is_pawn(occ.type) && occ.type != PT_PIKACHU)
            {
                add_mv(mv, n, p.row, p.col, ACT_ATTACK, r, c);
            }
            break;
        }
    }
}

// ---------------------------------------------------------------------------
// collect_sliding: fills separate emp[] and atk[] buffers matching Python's
// _sliding_squares() — empties and enemies separated, in direction order.
// ---------------------------------------------------------------------------

static void collect_sliding(State& s, Piece& p,
                             Move* emp, int& ne,
                             Move* atk, int& na,
                             const int dirs[][2], int ndirs)
{
    for (int d = 0; d < ndirs; d++) {
        int dr = dirs[d][0], dc = dirs[d][1];
        for (int r = p.row + dr, c = p.col + dc; in_bounds(r, c); r += dr, c += dc) {
            int8_t oidx = idx_at(s, r, c);
            if (oidx < 0) {
                add_mv(emp, ne, p.row, p.col, ACT_MOVE,   r, c);
            } else {
                Piece& occ = s.pieces[oidx];
                if (occ.team != p.team && !is_safetyball(occ.type))
                    add_mv(atk, na, p.row, p.col, ACT_ATTACK, r, c);
                break;
            }
        }
    }
}

// Adjacent squares that king already covers — used for deduplication in
// Vaporeon/Leafeon/Espeon.
static inline bool is_adj(const Piece& p, int r, int c) {
    int dr = r - (int)p.row, dc = c - (int)p.col;
    return dr >= -1 && dr <= 1 && dc >= -1 && dc <= 1;
}

// ---------------------------------------------------------------------------
// Per-type generators
// ---------------------------------------------------------------------------

// Forward Healball entry: non-pawn, non-Pikachu, injured piece can MOVE into
// the friendly empty Safetyball directly ahead.
static void forward_healball_entry(State& s, Piece& p, Move* mv, int& n) {
    int fr = (int)p.row + fwd(p.team);
    if (!in_bounds(fr, p.col)) return;
    int16_t mhp = MAX_HP[p.type];
    if (p.hp >= mhp) return; // not injured
    int8_t fidx = idx_at(s, fr, p.col);
    if (fidx < 0) return;
    Piece& fwd_p = s.pieces[fidx];
    if (!is_safetyball(fwd_p.type)) return;
    if (fwd_p.team != p.team) return;
    if (fwd_p.stored.type != PT_NONE) return;
    if (count_team(s, p.team) < 3) return;
    add_mv(mv, n, p.row, p.col, ACT_MOVE, (uint8_t)fr, p.col);
}

static void gen_squirtle(State& s, Piece& p, Move* mv, int& n) {
    // Python: [all MOVEs] then [all ATTACKs]
    static const int DIRS[4][2] = {{0,1},{0,-1},{1,0},{-1,0}};
    Move atk[8]; int na = 0;
    collect_sliding(s, p, mv, n, atk, na, DIRS, 4);
    for (int i = 0; i < na; i++) mv[n++] = atk[i];
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}
static void gen_charmander(State& s, Piece& p, Move* mv, int& n) {
    static const int J[8][2] = {
        {2,1},{2,-1},{-2,1},{-2,-1},{1,2},{1,-2},{-1,2},{-1,-2}
    };
    jumps<8>(s,p,mv,n,J);
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}
static void gen_bulbasaur(State& s, Piece& p, Move* mv, int& n) {
    // Python: [all MOVEs] then [all ATTACKs]
    static const int DIRS[4][2] = {{1,1},{1,-1},{-1,1},{-1,-1}};
    Move atk[8]; int na = 0;
    collect_sliding(s, p, mv, n, atk, na, DIRS, 4);
    for (int i = 0; i < na; i++) mv[n++] = atk[i];
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}

static void gen_mew(State& s, Piece& p, Move* mv, int& n) {
    // Python order: [all MOVEs] + [3×ATTACKs per enemy] + [FORESIGHT on all] + trades
    static const int DIRS[8][2] = {
        {0,1},{0,-1},{1,0},{-1,0},{1,1},{1,-1},{-1,1},{-1,-1}
    };
    Move emp[64], atk[32]; int ne = 0, na = 0;
    collect_sliding(s, p, emp, ne, atk, na, DIRS, 8);
    for (int i = 0; i < ne; i++) mv[n++] = emp[i];
    for (int i = 0; i < na; i++) {
        for (int slot = 0; slot < 3; slot++)
            add_mv(mv,n, atk[i].pr,atk[i].pc, ACT_ATTACK, atk[i].tr,atk[i].tc, 0,0, (int8_t)slot);
    }
    if (!s.fs_used[ti(p.team)]) {
        for (int i = 0; i < ne; i++)
            add_mv(mv,n, emp[i].pr,emp[i].pc, ACT_FORESIGHT, emp[i].tr,emp[i].tc);
        for (int i = 0; i < na; i++)
            add_mv(mv,n, atk[i].pr,atk[i].pc, ACT_FORESIGHT, atk[i].tr,atk[i].tc);
    }
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}

static void gen_pokeball(State& s, Piece& p, Move* mv, int& n) {
    int f = fwd(p.team);
    pawn_step(s,p,mv,n, f, 0,2); pawn_step(s,p,mv,n, 0, 1,2);
    pawn_step(s,p,mv,n, 0,-1,2); pawn_step(s,p,mv,n, f, 1,1);
    pawn_step(s,p,mv,n, f,-1,1);
}
static void gen_masterball(State& s, Piece& p, Move* mv, int& n) {
    int f = fwd(p.team);
    pawn_step(s,p,mv,n,  f, 0,2); pawn_step(s,p,mv,n,  0, 1,2);
    pawn_step(s,p,mv,n,  0,-1,2); pawn_step(s,p,mv,n,  f, 1,1);
    pawn_step(s,p,mv,n,  f,-1,1); pawn_step(s,p,mv,n, -f, 0,2);
    pawn_step(s,p,mv,n, -f, 1,1); pawn_step(s,p,mv,n, -f,-1,1);
}
static void gen_safetyball(State& s, Piece& p, Move* mv, int& n, bool master) {
    if (p.stored.type != PT_NONE)
        add_mv(mv,n, p.row,p.col, ACT_RELEASE, p.row,p.col);
    int f = fwd(p.team);
    step_sb(s,p,mv,n, f, 0,2); step_sb(s,p,mv,n, 0, 1,2);
    step_sb(s,p,mv,n, 0,-1,2); step_sb(s,p,mv,n, f, 1,1);
    step_sb(s,p,mv,n, f,-1,1);
    if (master) {
        step_sb(s,p,mv,n,-f, 0,2); step_sb(s,p,mv,n,-f, 1,1);
        step_sb(s,p,mv,n,-f,-1,1);
    }
}
static void gen_pikachu(State& s, Piece& p, Move* mv, int& n) {
    king_sq(s,p,mv,n);
    static const int EXT[8][2] = {
        {3,1},{3,-1},{-3,1},{-3,-1},{1,3},{1,-3},{-1,3},{-1,-3}
    };
    jumps<8>(s,p,mv,n,EXT);
    add_mv(mv,n, p.row,p.col, ACT_EVOLVE, p.row,p.col); // → Raichu
    trades(s,p,mv,n);
}
static void gen_raichu(State& s, Piece& p, Move* mv, int& n) {
    king_sq(s,p,mv,n);
    static const int EXT[8][2] = {
        {3,1},{3,-1},{-3,1},{-3,-1},{1,3},{1,-3},{-1,3},{-1,-3}
    };
    jumps<8>(s,p,mv,n,EXT);
    raichu_cardinals(s,p,mv,n);
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}

static void gen_qa(State& s, Piece& p, Move* mv, int& n) {
    // Quick Attack: attack king-adjacent enemy, then move king-range from post-attack pos.
    // QA always uses base 50 damage with the attacker's own type (matches Python _quick_attack_moves).
    static const int K[8][2] = {
        {-1,-1},{-1,0},{-1,1},{0,-1},{0,1},{1,-1},{1,0},{1,1}
    };
    for (auto& kd : K) {
        int ar = p.row + kd[0], ac = p.col + kd[1];
        if (!in_bounds(ar, ac)) continue;
        int8_t aidx = idx_at(s, ar, ac);
        if (aidx < 0) continue;
        Piece& target = s.pieces[aidx];
        if (target.team == p.team || is_pawn(target.type)) continue;

        // QA base 50, use attacker's own type (matches Python _quick_attack_moves)
        int m = MATCHUP_INT[POKE_TYPE[p.type]][POKE_TYPE[target.type]];
        int raw100 = 50 * m;
        int q = raw100 / 100, rem = raw100 % 100;
        int dmg = rem < 50 ? q*10 : (rem > 50 ? (q+1)*10 : (q%2==0 ? q*10 : (q+1)*10));
        dmg = dmg < 10 ? 10 : dmg;
        bool ko = (dmg >= target.hp);
        int post_r = ko ? ar : (int)p.row;
        int post_c = ko ? ac : (int)p.col;

        for (auto& md : K) {
            int dr = post_r + md[0], dc = post_c + md[1];
            if (!in_bounds(dr, dc)) continue;
            int8_t didx = idx_at(s, dr, dc);
            if (ko && dr == p.row && dc == p.col) didx = -1; // vacated
            if (didx < 0)
                add_mv(mv,n, p.row,p.col, ACT_QUICK_ATTACK, ar,ac, dr,dc);
        }
    }
}
static void gen_eevee(State& s, Piece& p, Move* mv, int& n) {
    king_sq(s,p,mv,n);
    gen_qa(s,p,mv,n);
    uint8_t evo = eevee_evo(p.item);
    if (evo != PT_NONE) {
        // slot encodes which evolution (Vaporeon=0..Espeon=4)
        int8_t slot = (int8_t)(p.item - ITEM_WATERSTONE); // WATERSTONE=2→0, ..., BENTSPOON=6→4
        add_mv(mv,n, p.row,p.col, ACT_EVOLVE, p.row,p.col, 0,0, slot);
    }
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}
static void gen_vaporeon(State& s, Piece& p, Move* mv, int& n) {
    // Python: [king] + [rook MOVEs not adj] + [rook ATTACKs not adj] + QA + forward_healball + trades
    king_sq(s,p,mv,n);
    static const int DIRS[4][2] = {{0,1},{0,-1},{1,0},{-1,0}};
    Move emp[64], atk[8]; int ne = 0, na = 0;
    collect_sliding(s, p, emp, ne, atk, na, DIRS, 4);
    for (int i = 0; i < ne; i++) if (!is_adj(p, emp[i].tr, emp[i].tc)) mv[n++] = emp[i];
    for (int i = 0; i < na; i++) if (!is_adj(p, atk[i].tr, atk[i].tc)) mv[n++] = atk[i];
    gen_qa(s,p,mv,n);
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}
static void gen_flareon(State& s, Piece& p, Move* mv, int& n) {
    // Python: king + knight jumps + QA + forward_healball + trades
    king_sq(s,p,mv,n);
    static const int J[8][2] = {
        {2,1},{2,-1},{-2,1},{-2,-1},{1,2},{1,-2},{-1,2},{-1,-2}
    };
    jumps<8>(s,p,mv,n,J);
    gen_qa(s,p,mv,n);
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}
static void gen_leafeon(State& s, Piece& p, Move* mv, int& n) {
    // Python: [king] + [bishop MOVEs not adj] + [bishop ATTACKs not adj] + QA + forward_healball + trades
    king_sq(s,p,mv,n);
    static const int DIRS[4][2] = {{1,1},{1,-1},{-1,1},{-1,-1}};
    Move emp[64], atk[8]; int ne = 0, na = 0;
    collect_sliding(s, p, emp, ne, atk, na, DIRS, 4);
    for (int i = 0; i < ne; i++) if (!is_adj(p, emp[i].tr, emp[i].tc)) mv[n++] = emp[i];
    for (int i = 0; i < na; i++) if (!is_adj(p, atk[i].tr, atk[i].tc)) mv[n++] = atk[i];
    gen_qa(s,p,mv,n);
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}
static void gen_jolteon(State& s, Piece& p, Move* mv, int& n) {
    // Python: king + L-jumps + unobstructed 2-sq cardinal jumps + 2-sq diagonal jumps + QA + forward_healball + trades
    king_sq(s,p,mv,n);
    static const int EXT[8][2] = {
        {3,1},{3,-1},{-3,1},{-3,-1},{1,3},{1,-3},{-1,3},{-1,-3}
    };
    jumps<8>(s,p,mv,n,EXT);
    raichu_cardinals(s,p,mv,n);
    static const int DIAG[4][2] = {{2,2},{2,-2},{-2,2},{-2,-2}};
    jumps<4>(s,p,mv,n,DIAG);
    gen_qa(s,p,mv,n);
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}
static void gen_espeon(State& s, Piece& p, Move* mv, int& n) {
    // Python: MOVE only (no ATTACK) + FORESIGHT on all queen-range squares + PSYWAVE + trades
    // King adjacency: MOVE only (filter out ATTACK from king_sq)
    static const int K[8][2] = {
        {-1,-1},{-1,0},{-1,1},{0,-1},{0,1},{1,-1},{1,0},{1,1}
    };
    for (auto& kd : K) {
        int r = p.row + kd[0], c = p.col + kd[1];
        if (!in_bounds(r,c)) continue;
        if (idx_at(s,r,c) < 0)
            add_mv(mv,n, p.row,p.col, ACT_MOVE, r,c);
        // no ATTACK added for Espeon
    }
    static const int DIRS[8][2] = {
        {0,1},{0,-1},{1,0},{-1,0},{1,1},{1,-1},{-1,1},{-1,-1}
    };
    Move emp[64], atk[32]; int ne = 0, na = 0;
    collect_sliding(s, p, emp, ne, atk, na, DIRS, 8);
    for (int i = 0; i < ne; i++) if (!is_adj(p, emp[i].tr, emp[i].tc)) mv[n++] = emp[i];
    // no ATTACK slides added
    if (!s.fs_used[ti(p.team)]) {
        for (int i = 0; i < ne; i++)
            add_mv(mv,n, emp[i].pr,emp[i].pc, ACT_FORESIGHT, emp[i].tr,emp[i].tc);
        for (int i = 0; i < na; i++)
            add_mv(mv,n, atk[i].pr,atk[i].pc, ACT_FORESIGHT, atk[i].tr,atk[i].tc);
    }
    // PSYWAVE: no explicit target — encode as Espeon's own square (sentinel)
    add_mv(mv,n, p.row,p.col, ACT_PSYWAVE, p.row,p.col);
    forward_healball_entry(s,p,mv,n);
    trades(s,p,mv,n);
}

// ---------------------------------------------------------------------------
// get_legal_moves
// ---------------------------------------------------------------------------

static int get_legal_moves(State& s, Move* mv) {
    // Iterate in board row-major order to match Python's all_pieces() iteration order.
    // (Python: for row in board: for cell in row: if cell is not None and team matches)
    int n = 0;
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            int8_t idx = s.board[r][c];
            if (idx < 0) continue;
            Piece& p = s.pieces[idx];
            if (p.type == PT_NONE || p.team != s.active) continue;
            switch (p.type) {
            case PT_SQUIRTLE:          gen_squirtle(s,p,mv,n);  break;
            case PT_CHARMANDER:        gen_charmander(s,p,mv,n); break;
            case PT_BULBASAUR:         gen_bulbasaur(s,p,mv,n);  break;
            case PT_MEW:               gen_mew(s,p,mv,n);        break;
            case PT_POKEBALL:          gen_pokeball(s,p,mv,n);   break;
            case PT_MASTERBALL:        gen_masterball(s,p,mv,n); break;
            case PT_SAFETYBALL:        gen_safetyball(s,p,mv,n,false); break;
            case PT_MASTER_SAFETYBALL: gen_safetyball(s,p,mv,n,true);  break;
            case PT_PIKACHU:           gen_pikachu(s,p,mv,n);   break;
            case PT_RAICHU:            gen_raichu(s,p,mv,n);    break;
            case PT_EEVEE:             gen_eevee(s,p,mv,n);     break;
            case PT_VAPOREON:          gen_vaporeon(s,p,mv,n);  break;
            case PT_FLAREON:           gen_flareon(s,p,mv,n);   break;
            case PT_LEAFEON:           gen_leafeon(s,p,mv,n);   break;
            case PT_JOLTEON:           gen_jolteon(s,p,mv,n);   break;
            case PT_ESPEON:            gen_espeon(s,p,mv,n);    break;
            }
        }
    }
    return n;
}

// ---------------------------------------------------------------------------
// apply_move — modifies state in place.
// 'roll' is used for pokeball stochastic outcome (0..1): < catch_prob = capture.
// ---------------------------------------------------------------------------

static void check_promotion(Piece& p) {
    int promo = (p.team == TEAM_RED) ? 7 : 0;
    if ((int)p.row == promo) {
        if (p.type == PT_POKEBALL)   p.type = PT_MASTERBALL;
        if (p.type == PT_SAFETYBALL) p.type = PT_MASTER_SAFETYBALL;
    }
}

// Move piece at pidx to (r,c); update board.
static void move_piece(State& s, int pidx, int r, int c) {
    Piece& p = s.pieces[pidx];
    s.board[p.row][p.col] = -1;
    p.row = (uint8_t)r; p.col = (uint8_t)c;
    s.board[r][c] = (int8_t)pidx;
}

// Kill piece at tidx; clear board.
static void kill_piece(State& s, int tidx) {
    Piece& t = s.pieces[tidx];
    s.board[t.row][t.col] = -1;
    t.type = PT_NONE;
}

// Safetyball heal: heal stored piece; auto-release if full HP.
// Returns true if auto-released (safetyball is consumed).
static bool sb_heal(State& s, int pidx) {
    Piece& p = s.pieces[pidx];
    StoredPiece& st = p.stored;
    int16_t mhp = MAX_HP[st.type];
    if (p.type == PT_MASTER_SAFETYBALL) {
        bool already_full = (st.hp >= mhp);
        st.hp = mhp;
        if (already_full) {
            // Already at full HP (healed on entry last turn) — auto-release.
            int new_idx = alloc_slot(s, pidx);
            if (new_idx >= 0) {
                Piece& np = s.pieces[new_idx];
                np.type = st.type; np.team = st.team;
                np.row = p.row;    np.col = p.col;
                np.hp  = st.hp;    np.item = st.item;
                np.stored = {};
                s.board[p.row][p.col] = (int8_t)new_idx;
            }
            st.type = PT_NONE;
            p.type  = PT_NONE;
            return true;
        }
        return false;
    }
    int16_t heal = mhp / 4;
    st.hp = std::min((int16_t)(st.hp + heal), mhp);
    if (st.hp >= mhp) {
        // Auto-release: stored piece takes safetyball's position; safetyball consumed.
        int new_idx = alloc_slot(s, pidx);
        if (new_idx >= 0) {
            Piece& np = s.pieces[new_idx];
            np.type = st.type; np.team = st.team;
            np.row = p.row;    np.col = p.col;
            np.hp  = st.hp;    np.item = st.item;
            np.stored = {};
            s.board[p.row][p.col] = (int8_t)new_idx;
        }
        st.type = PT_NONE;
        p.type  = PT_NONE; // safetyball consumed
        return true;
    }
    return false;
}

static void advance_turn(State& s) {
    s.active = other_team(s.active);
    s.turn++;
}

// Discharge stored Pokémon from any safetyball of the active player that was not
// moved this turn.  A safetyball must be moved each turn to retain its passenger;
// if the owner acts elsewhere the stored piece is immediately discharged (same as
// the auto-release-at-full-HP path: safetyball consumed, piece placed on its square).
static void discharge_unmoved_safetyballs(State& s, uint8_t moved_type) {
    if (is_safetyball(moved_type)) return; // player moved a safetyball — no discharge
    for (int i = 0; i < s.n_pieces; ++i) {
        Piece& p = s.pieces[i];
        if (p.type == PT_NONE) continue;
        if (p.team != s.active) continue;
        if (!is_safetyball(p.type)) continue;
        if (p.stored.type == PT_NONE) continue;
        // Release stored piece at safetyball's position; safetyball consumed
        int new_idx = alloc_slot(s, i);
        if (new_idx >= 0) {
            Piece& np  = s.pieces[new_idx];
            np.type    = p.stored.type;
            np.team    = p.stored.team;
            np.row     = p.row;
            np.col     = p.col;
            np.hp      = p.stored.hp;
            np.item    = p.stored.item;
            np.stored  = {};
            s.board[p.row][p.col] = (int8_t)new_idx;
        }
        p.stored.type = PT_NONE;
        p.type        = PT_NONE; // safetyball consumed
    }
}

static void apply_move(State& s, const Move& mv, float roll) {
    // Resolve pending foresight, reset foresight-used flag.
    resolve_foresight(s);
    s.fs_used[ti(s.active)] = 0;

    int8_t pidx8 = idx_at(s, mv.pr, mv.pc);
    if (pidx8 < 0) { advance_turn(s); return; }
    int pidx = (int)pidx8;
    Piece& p = s.pieces[pidx];
    // Save the type of the piece that will act, before any handler may clear it.
    // Used by discharge_unmoved_safetyballs to determine if a safetyball was moved.
    const uint8_t moved_type = p.type;

    // ── POKEBALL stochastic ──────────────────────────────────────────────────
    if (mv.action == ACT_ATTACK && p.type == PT_POKEBALL) {
        int8_t t8 = idx_at(s, mv.tr, mv.tc);
        if (t8 < 0) {
            // Target gone (foresight resolved this turn) — failure
            s.board[mv.pr][mv.pc] = -1; p.type = PT_NONE;
            s.has_traded[ti(s.active)] = 0;
            discharge_unmoved_safetyballs(s, moved_type);
            advance_turn(s); return;
        }
        Piece& tgt = s.pieces[t8];
        if (is_safetyball(tgt.type) || tgt.type == PT_PIKACHU) {
            // Immune — pokeball survives, just fail
            s.has_traded[ti(s.active)] = 0;
            discharge_unmoved_safetyballs(s, moved_type);
            advance_turn(s); return;
        }
        {
            int16_t mhp = MAX_HP[tgt.type];
            float ratio = (mhp > 0) ? (float)tgt.hp / (float)mhp : 1.0f;
            float prob;
            if (tgt.type == PT_MEW) {
                prob = (ratio >= 1.0f) ? 0.20f : (ratio >= 0.5f) ? 0.40f : 0.60f;
            } else {
                prob = (ratio >= 1.0f) ? 0.25f : (ratio >= 0.5f) ? 0.50f : 0.75f;
            }
            if (roll < prob) {
                // Capture: both disappear
                kill_piece(s, pidx);
                kill_piece(s, (int)t8);
            } else {
                // Fail: pokeball disappears only, target unchanged
                s.board[mv.pr][mv.pc] = -1; p.type = PT_NONE;
            }
        }
        s.has_traded[ti(s.active)] = 0;
        discharge_unmoved_safetyballs(s, moved_type);
        advance_turn(s); return;
    }

    // ── TRADE ───────────────────────────────────────────────────────────────
    if (mv.action == ACT_TRADE) {
        int8_t n8 = idx_at(s, mv.tr, mv.tc);
        if (n8 < 0) { advance_turn(s); return; }
        Piece& nb = s.pieces[n8];
        std::swap(p.item, nb.item);
        // Eevee auto-evolve
        if (nb.type == PT_EEVEE) {
            uint8_t evo = eevee_evo(nb.item);
            if (evo != PT_NONE) {
                int16_t gain = MAX_HP[evo] - MAX_HP[PT_EEVEE];
                nb.type = evo;
                nb.hp   = std::min((int16_t)(nb.hp + gain), MAX_HP[evo]);
                nb.item = ITEM_NONE;
                s.has_traded[ti(s.active)] = 0;
                discharge_unmoved_safetyballs(s, moved_type);
                advance_turn(s); return;
            }
        }
        s.has_traded[ti(s.active)] = 1; // trade done; turn NOT advanced
        return;
    }

    // ── EVOLVE ──────────────────────────────────────────────────────────────
    if (mv.action == ACT_EVOLVE) {
        if (p.type == PT_PIKACHU) {
            int16_t gain = MAX_HP[PT_RAICHU] - MAX_HP[PT_PIKACHU];
            p.type = PT_RAICHU;
            p.hp   = std::min((int16_t)(p.hp + gain), MAX_HP[PT_RAICHU]);
            p.item = ITEM_NONE;
        } else if (p.type == PT_EEVEE) {
            uint8_t evo = eevee_evo(p.item);
            if (evo != PT_NONE) {
                int16_t gain = MAX_HP[evo] - MAX_HP[PT_EEVEE];
                p.type = evo;
                p.hp   = std::min((int16_t)(p.hp + gain), MAX_HP[evo]);
                p.item = ITEM_NONE;
            }
        }
        s.has_traded[ti(s.active)] = 0;
        discharge_unmoved_safetyballs(s, moved_type);
        advance_turn(s); return;
    }

    // ── FORESIGHT ───────────────────────────────────────────────────────────
    if (mv.action == ACT_FORESIGHT) {
        int16_t dmg = (p.type == PT_MEW || p.type == PT_ESPEON) ? 120 : 80;
        Foresight& fx = s.foresight[ti(s.active)];
        fx.active = true; fx.row = mv.tr; fx.col = mv.tc;
        fx.damage = dmg;  fx.resolves_on_turn = s.turn + 2;
        s.fs_used[ti(s.active)] = 1;
        s.has_traded[ti(s.active)] = 0;
        discharge_unmoved_safetyballs(s, moved_type);
        advance_turn(s); return;
    }

    // ── RELEASE (safetyball manually releases stored piece) ─────────────────
    if (mv.action == ACT_RELEASE) {
        StoredPiece& st = p.stored;
        int new_idx = alloc_slot(s, pidx);
        if (new_idx >= 0) {
            Piece& np = s.pieces[new_idx];
            np.type = st.type; np.team = st.team;
            np.row = p.row;    np.col = p.col;
            np.hp  = st.hp;    np.item = st.item;
            np.stored = {};
            s.board[p.row][p.col] = (int8_t)new_idx;
            st.type = PT_NONE;
            // Safetyball is consumed (same as auto-release)
            p.type = PT_NONE;
        }
        s.has_traded[ti(s.active)] = 0;
        // moved_type is PT_SAFETYBALL/PT_MASTER_SAFETYBALL → discharge is a no-op
        discharge_unmoved_safetyballs(s, moved_type);
        advance_turn(s); return;
    }

    // ── MOVE ────────────────────────────────────────────────────────────────
    if (mv.action == ACT_MOVE) {
        int8_t old_tidx = idx_at(s, mv.tr, mv.tc); // may be an injured ally (safetyball) or safetyball
        // Pokemon-enters-Healball: non-pawn, non-Pikachu moving into a friendly empty safetyball
        if (!is_pawn(p.type) && p.type != PT_PIKACHU && old_tidx >= 0) {
            Piece& tgt = s.pieces[old_tidx];
            if (is_safetyball(tgt.type) && tgt.team == p.team && tgt.stored.type == PT_NONE) {
                tgt.stored = {p.type, p.team, p.item, p.hp};
                s.board[p.row][p.col] = -1;
                p.type = PT_NONE;
                sb_heal(s, (int)old_tidx); // initial heal
                s.has_traded[ti(s.active)] = 0;
                // Pass the Safetyball's type so discharge treats this as a Safetyball move,
                // preventing the just-stored Pokemon from being immediately expelled.
                discharge_unmoved_safetyballs(s, tgt.type);
                advance_turn(s); return;
            }
        }
        move_piece(s, pidx, mv.tr, mv.tc);
        if (is_pawn(p.type)) check_promotion(p);
        if (is_safetyball(p.type)) {
            if (old_tidx >= 0 && s.pieces[old_tidx].team == p.team &&
                p.stored.type == PT_NONE)
            {
                // Store the ally
                Piece& ally = s.pieces[old_tidx];
                p.stored = {ally.type, ally.team, ally.item, ally.hp};
                ally.type = PT_NONE; // remove from pieces
                sb_heal(s, pidx);    // initial heal
            } else if (p.stored.type != PT_NONE) {
                sb_heal(s, pidx); // carry-move heal
            }
        }
        s.has_traded[ti(s.active)] = 0;
        // If moved_type is safetyball, discharge is a no-op; otherwise discharges others.
        discharge_unmoved_safetyballs(s, moved_type);
        advance_turn(s); return;
    }

    // ── ATTACK ──────────────────────────────────────────────────────────────
    if (mv.action == ACT_ATTACK) {
        int8_t t8 = idx_at(s, mv.tr, mv.tc);
        if (t8 < 0) {
            discharge_unmoved_safetyballs(s, moved_type);
            advance_turn(s); return;
        }
        Piece& tgt = s.pieces[t8];
        if (is_safetyball(tgt.type)) {
            discharge_unmoved_safetyballs(s, moved_type);
            advance_turn(s); return;
        }

        if (p.type == PT_MASTERBALL || is_pawn(tgt.type)) {
            // Pikachu is immune to regular pokeballs — pokeball destroyed, Pikachu advances
            if (p.type == PT_PIKACHU && tgt.type == PT_POKEBALL) {
                kill_piece(s, (int)t8);
                move_piece(s, pidx, mv.tr, mv.tc);
            } else {
                // Capture: both disappear
                kill_piece(s, pidx);
                kill_piece(s, (int)t8);
            }
        } else {
            int dmg = calc_damage(p.type, tgt.type, mv.slot);
            tgt.hp -= (int16_t)dmg;
            if (tgt.hp <= 0) {
                kill_piece(s, (int)t8);
                move_piece(s, pidx, mv.tr, mv.tc);
                if (is_pawn(p.type)) check_promotion(p);
            }
            // Flareon recoil after regular attack
            if (p.type == PT_FLAREON) {
                p.hp -= 40;
                if (p.hp <= 0) {
                    s.board[p.row][p.col] = -1;
                    p.type = PT_NONE;
                }
            }
            // Non-lethal: attacker stays
        }
        s.has_traded[ti(s.active)] = 0;
        discharge_unmoved_safetyballs(s, moved_type);
        advance_turn(s); return;
    }

    // ── QUICK_ATTACK ────────────────────────────────────────────────────────
    if (mv.action == ACT_QUICK_ATTACK) {
        int8_t t8 = idx_at(s, mv.tr, mv.tc);
        if (t8 >= 0) {
            Piece& tgt = s.pieces[t8];
            // QA base 50, attacker's own type (matches Python rules.py _do_quick_attack)
            int m2 = MATCHUP_INT[POKE_TYPE[p.type]][POKE_TYPE[tgt.type]];
            int r2 = 50 * m2, q2 = r2/100, rem2 = r2%100;
            int dmg = rem2 < 50 ? q2*10 : (rem2 > 50 ? (q2+1)*10 : (q2%2==0 ? q2*10 : (q2+1)*10));
            if (dmg < 10) dmg = 10;
            tgt.hp -= (int16_t)dmg;
            if (tgt.hp <= 0) {
                kill_piece(s, (int)t8);
                move_piece(s, pidx, mv.tr, mv.tc); // Eevee occupies vacated square
            }
        }
        // Secondary move (always present for QUICK_ATTACK)
        move_piece(s, pidx, mv.sr, mv.sc);
        s.has_traded[ti(s.active)] = 0;
        discharge_unmoved_safetyballs(s, moved_type);
        advance_turn(s); return;
    }

    // Fallthrough: unknown action, just advance turn
    s.has_traded[ti(s.active)] = 0;
    discharge_unmoved_safetyballs(s, moved_type);
    advance_turn(s);
}

// ---------------------------------------------------------------------------
// Terminal check and HP winner
// ---------------------------------------------------------------------------

static int is_terminal(const State& s) {
    bool red_alive = false, blue_alive = false;
    for (int i = 0; i < s.n_pieces; i++) {
        const Piece& p = s.pieces[i];
        if (p.type == PT_NONE) continue;
        if (is_king(p.type)) {
            if (p.team == TEAM_RED) red_alive  = true;
            else                    blue_alive = true;
        }
        // Kings stored inside safetyballs are alive (healing, not eliminated)
        if (p.stored.type != PT_NONE && is_king(p.stored.type)) {
            if (p.stored.team == TEAM_RED) red_alive  = true;
            else                           blue_alive = true;
        }
    }
    if (red_alive && blue_alive) return WIN_NONE;
    if (!red_alive && !blue_alive) return WIN_DRAW;
    return red_alive ? WIN_RED : WIN_BLUE;
}

static int hp_winner(const State& s) {
    int red = 0, blue = 0;
    static const int PAWN_VAL[9] = {0, 0,0,0,0, 50,200,50,200};
    for (int i = 0; i < s.n_pieces; i++) {
        const Piece& p = s.pieces[i];
        if (p.type == PT_NONE) continue;
        int hp = is_pawn(p.type) ? PAWN_VAL[p.type] : (int)p.hp;
        if (p.stored.type != PT_NONE) hp += p.stored.hp;
        if (p.team == TEAM_RED) red += hp; else blue += hp;
    }
    if (red > blue) return WIN_RED;
    if (blue > red) return WIN_BLUE;
    return WIN_DRAW;
}

// ---------------------------------------------------------------------------
// XorShift64
// ---------------------------------------------------------------------------

struct XorShift64 {
    uint64_t s;
    XorShift64(uint64_t seed) : s(seed ? seed : 1ULL) {}
    inline float next_float() {
        s ^= s << 13; s ^= s >> 7; s ^= s << 17;
        return (float)(s & 0xFFFFFF) * (1.0f / 16777216.0f);
    }
    inline int next_int(int n) {
        return n <= 1 ? 0 : (int)(next_float() * (float)n) % n;
    }
};

// ---------------------------------------------------------------------------
// Rollout loop
// ---------------------------------------------------------------------------

static int rollout(State s, int depth, XorShift64& rng) {
    Move moves[1024];
    for (int d = 0; d < depth; d++) {
        int term = is_terminal(s);
        if (term) return term;
        int n = get_legal_moves(s, moves);
        if (n == 0) return WIN_DRAW;
        apply_move(s, moves[rng.next_int(n)], rng.next_float());
    }
    return hp_winner(s);
}

static int rollout_fixed(State s, const std::vector<float>& rolls, int depth) {
    Move moves[1024];
    size_t ri = 0;
    for (int d = 0; d < depth; d++) {
        int term = is_terminal(s);
        if (term) return term;
        int n = get_legal_moves(s, moves);
        if (n == 0) return WIN_DRAW;
        float mroll = ri < rolls.size() ? rolls[ri++] : 0.0f;
        float proll = ri < rolls.size() ? rolls[ri++] : 1.0f;
        apply_move(s, moves[(int)(mroll * n) % n], proll);
    }
    return hp_winner(s);
}

// ---------------------------------------------------------------------------
// Python-facing functions
// ---------------------------------------------------------------------------

static std::tuple<int,int,int> run_rollouts(
    py::bytes state_bytes, int n_rollouts, int depth_limit, uint64_t seed)
{
    std::string buf = state_bytes;
    State base = decode_state(buf.data(), (int)buf.size());
    int red = 0, blue = 0, draws = 0;
    XorShift64 rng(seed);
    for (int i = 0; i < n_rollouts; i++) {
        int r = rollout(base, depth_limit, rng);
        if      (r == WIN_RED)  red++;
        else if (r == WIN_BLUE) blue++;
        else                    draws++;
    }
    return std::make_tuple(red, blue, draws);
}

static int run_rollout_with_rolls(
    py::bytes state_bytes, std::vector<float> rolls, int depth_limit)
{
    std::string buf = state_bytes;
    State base = decode_state(buf.data(), (int)buf.size());
    int r = rollout_fixed(base, rolls, depth_limit);
    return r == WIN_RED ? 1 : 0;
}

// ---------------------------------------------------------------------------
// pybind11 module
// ---------------------------------------------------------------------------

// Debug: return (n_moves, move descriptions) for the first step
static py::list debug_moves(py::bytes state_bytes) {
    std::string buf = state_bytes;
    State s = decode_state(buf.data(), (int)buf.size());
    Move mv[1024]; int n = get_legal_moves(s, mv);
    py::list result;
    for (int i = 0; i < n; i++) {
        result.append(py::make_tuple(
            (int)mv[i].pr, (int)mv[i].pc,
            (int)mv[i].action,
            (int)mv[i].tr, (int)mv[i].tc,
            (int)mv[i].sr, (int)mv[i].sc,
            (int)mv[i].slot
        ));
    }
    return result;
}

static py::list debug_state_after_n(py::bytes state_bytes, std::vector<float> rolls, int n_steps) {
    std::string buf(state_bytes);
    State s = decode_state(buf.data(), (int)buf.size());
    size_t ri = 0;
    Move moves[1024];
    for (int d = 0; d < n_steps; d++) {
        if (is_terminal(s)) break;
        int n = get_legal_moves(s, moves);
        if (n == 0) break;
        float mroll = ri < rolls.size() ? rolls[ri++] : 0.0f;
        float proll = ri < rolls.size() ? rolls[ri++] : 1.0f;
        apply_move(s, moves[(int)(mroll * n) % n], proll);
    }
    py::list result;
    for (int i = 0; i < s.n_pieces; i++) {
        const Piece& p = s.pieces[i];
        if (p.type == PT_NONE) continue;
        result.append(py::make_tuple(
            (int)p.type, (int)p.team, (int)p.row, (int)p.col,
            (int)p.hp, (int)p.item,
            (int)p.stored.type, (int)p.stored.hp
        ));
    }
    return result;
}

PYBIND11_MODULE(pokechess_cpp, m) {
    m.doc() = "PokeChess C++ rollout engine";

    m.def("run_rollouts", &run_rollouts,
          py::arg("state_bytes"),
          py::arg("n_rollouts"),
          py::arg("depth_limit") = 150,
          py::arg("seed") = (uint64_t)42,
          py::call_guard<py::gil_scoped_release>(),
          "Run N rollouts. Returns (red_wins, blue_wins, draws).");

    m.def("debug_moves", &debug_moves, "Return (pr,pc,action,tr,tc,sr,sc,slot) for each legal move.");

    m.def("run_rollout_with_rolls", &run_rollout_with_rolls,
          py::arg("state_bytes"),
          py::arg("rolls"),
          py::arg("depth_limit") = 150,
          "Deterministic rollout with pre-supplied floats. Returns 1=RED win, 0=BLUE/draw.");

    m.def("debug_state_after_n", &debug_state_after_n,
          py::arg("state_bytes"),
          py::arg("rolls"),
          py::arg("n_steps"),
          "Apply n_steps from state with pre-supplied rolls. Returns list of (type,team,row,col,hp,item,stored_type,stored_hp).");
}
