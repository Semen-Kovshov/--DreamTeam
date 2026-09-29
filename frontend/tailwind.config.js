/** Палитра «хвоя» — дизайн-комплект v1 (design/handoff-hvoya/handoff/tokens.css). */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "#f9f9f7",
        surface: "#fcfcfb",
        fill: "#f4f3ef",
        ink: {
          DEFAULT: "#0b0b0b",
          secondary: "#52514e",
          muted: "#898781",
        },
        line: "#e1e0d9",
        linein: "#edece6",
        baseline: "#c3c2b7",
        accent: {
          DEFAULT: "#1f7a6f",
          deep: "#14594f",
          soft: "#d5ece6",
          tint: "#e6f1ee",
        },
        good: "#5f9c53",
        goodtext: "#14594f",
        warn: "#d9a12b",
        warntext: "#a8760c",
        serious: "#d97a3f",
        critical: "#c04b3c",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "Segoe UI", "sans-serif"],
        // Одна гарнитура на весь интерфейс: «моноширинные» блоки — тот же
        // Plex Sans с табличными цифрами (font-mono остаётся как роль).
        mono: ["IBM Plex Sans", "system-ui", "Segoe UI", "sans-serif"],
      },
      borderRadius: {
        window: "18px",
        card: "14px",
        btn: "12px",
      },
      boxShadow: {
        window: "0 18px 44px rgba(10,12,18,.32)",
        card: "0 8px 24px rgba(10,12,18,.18)",
        btn: "0 2px 8px rgba(31,122,111,.4)",
        tab: "0 4px 12px rgba(10,12,18,.14)",
        panel: "-24px 0 60px rgba(0,0,0,.35)",
      },
    },
  },
  plugins: [],
};
