export const POLL_INTERVAL_MS = 2500;


export const PIECE_TYPE_LABELS: Record<string, string> = {
  SQUIRTLE: "Squirtle",
  CHARMANDER: "Charmander",
  BULBASAUR: "Bulbasaur",
  MEW: "Mew",
  PIKACHU: "Pikachu",
  RAICHU: "Raichu",
  EEVEE: "Eevee",
  VAPOREON: "Vaporeon",
  FLAREON: "Flareon",
  LEAFEON: "Leafeon",
  JOLTEON: "Jolteon",
  ESPEON: "Espeon",
  POKEBALL: "Pokéball",
  MASTERBALL: "Masterball",
  SAFETYBALL: "Safetyball",
  MASTER_SAFETYBALL: "Master Safetyball",
};

export const PIECE_TYPE_EMOJIS: Record<string, string> = {
  SQUIRTLE: "💧",
  CHARMANDER: "🔥",
  BULBASAUR: "🌿",
  MEW: "🌀",
  PIKACHU: "⚡",
  RAICHU: "⚡",
  EEVEE: "🌟",
  VAPOREON: "💧",
  FLAREON: "🔥",
  LEAFEON: "🌿",
  JOLTEON: "⚡",
  ESPEON: "🔮",
  POKEBALL: "⚪",
  MASTERBALL: "🟣",
  SAFETYBALL: "🛡️",
  MASTER_SAFETYBALL: "🛡️",
};

export const POKEMON_TYPE_COLORS: Record<string, string> = {
  WATER: "#5EAEFF",
  FIRE: "#FF6B35",
  GRASS: "#4CAF50",
  PSYCHIC: "#E040FB",
  ELECTRIC: "#FFD600",
  NORMAL: "#BDBDBD",
};

export const POKEMON_TYPE_FOR_PIECE: Record<string, string> = {
  SQUIRTLE: "WATER",
  CHARMANDER: "FIRE",
  BULBASAUR: "GRASS",
  MEW: "PSYCHIC",
  PIKACHU: "ELECTRIC",
  RAICHU: "ELECTRIC",
  EEVEE: "NORMAL",
  VAPOREON: "WATER",
  FLAREON: "FIRE",
  LEAFEON: "GRASS",
  JOLTEON: "ELECTRIC",
  ESPEON: "PSYCHIC",
};

export const EEVEE_EVOLUTIONS = [
  { slot: 0, name: "Vaporeon", emoji: "💧" },
  { slot: 1, name: "Flareon", emoji: "🔥" },
  { slot: 2, name: "Leafeon", emoji: "🌿" },
  { slot: 3, name: "Jolteon", emoji: "⚡" },
  { slot: 4, name: "Espeon", emoji: "🔮" },
];

export const MAX_HP: Record<string, number> = {
  SQUIRTLE: 200,
  CHARMANDER: 200,
  BULBASAUR: 200,
  MEW: 250,
  PIKACHU: 200,
  RAICHU: 250,
  EEVEE: 120,
  VAPOREON: 220,
  FLAREON: 220,
  LEAFEON: 220,
  JOLTEON: 220,
  ESPEON: 220,
  POKEBALL: 1,
  MASTERBALL: 1,
  SAFETYBALL: 1,
  MASTER_SAFETYBALL: 1,
};
