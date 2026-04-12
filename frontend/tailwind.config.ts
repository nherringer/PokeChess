import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "bg-deep": "#12141E",
        "bg-panel": "#191B26",
        "bg-card": "#232638",
        "red-team": "#E03737",
        "blue-team": "#3C72E0",
        "hl-select": "#64A0FF",
        "hl-move": "#F5E028",
        "hl-attack": "#F55A19",
        "hl-foresight": "#32D7FA",
        "hl-trade": "#A855F7",
        "accent-gold": "#FFD700",
        "type-water": "#5EAEFF",
        "type-fire": "#FF6B35",
        "type-grass": "#4CAF50",
        "type-psychic": "#E040FB",
        "type-electric": "#FFD600",
        "type-normal": "#BDBDBD",
        "board-light": "#EBF0CE",
        "board-dark": "#6E8F52",
      },
      fontFamily: {
        display: ["Fredoka One", "Nunito", "sans-serif"],
        body: ["Nunito", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
