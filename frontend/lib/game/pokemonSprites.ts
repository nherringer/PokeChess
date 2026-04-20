/**
 * Local sprites copied from `demo/sprites/` (same dex filenames as pokechess_ui.py).
 * Pokeball piece types have no artwork there — callers should fall back to emoji/UI.
 */
const DEX_BY_KEY: Record<string, number> = {
  BULBASAUR: 1,
  CHARMANDER: 4,
  SQUIRTLE: 7,
  PIKACHU: 25,
  RAICHU: 26,
  EEVEE: 133,
  VAPOREON: 134,
  JOLTEON: 135,
  FLAREON: 136,
  MEW: 151,
  ESPEON: 196,
  LEAFEON: 470,
};

export function pokemonDexNumber(speciesOrPieceType: string): number | null {
  const key = speciesOrPieceType.trim().toUpperCase();
  const n = DEX_BY_KEY[key];
  return n !== undefined ? n : null;
}

/** Path under `/public`, e.g. `/sprites/pokemon/25.png` */
export function pokemonSpriteSrc(speciesOrPieceType: string): string | null {
  const dex = pokemonDexNumber(speciesOrPieceType);
  if (dex === null) return null;
  return `/sprites/pokemon/${dex}.png`;
}
