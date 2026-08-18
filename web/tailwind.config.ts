import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#1B140F",
        roast: "#332419",
        oat: "#EDE3D0",
        scan: "#4FBEB0",
        amber: "#E3A93F",
        ember: "#D2622E",
      },
      fontFamily: {
        mono: ['"Space Mono"', "monospace"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
      },
      fontSize: {
        "hero-number": ["clamp(3rem, 8vw, 4.5rem)", { lineHeight: "1.1", fontWeight: "700" }],
        "table-title": ["1.125rem", { lineHeight: "1.4", fontWeight: "500" }],
        caption: ["0.8125rem", { lineHeight: "1.5", fontWeight: "400" }],
      },
      keyframes: {
        scanline: {
          "0%": { transform: "translateY(-100%)", opacity: "0.6" },
          "100%": { transform: "translateY(100%)", opacity: "0" },
        },
        "viewfinder-lock": {
          "0%": { padding: "0.75rem" },
          "100%": { padding: "0.5rem" },
        },
        "fill-bar": {
          "0%": { width: "0%" },
          "100%": { width: "var(--fill-width)" },
        },
      },
      animation: {
        scanline: "scanline 1.2s ease-out forwards",
        "viewfinder-lock": "viewfinder-lock 150ms ease-out forwards",
        "fill-bar": "fill-bar 0.8s ease-out forwards",
      },
    },
  },
  plugins: [],
};

export default config;
