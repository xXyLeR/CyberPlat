/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0A0D12",       // fundo principal
        panel: "#121820",      // painéis/cards
        "panel-raised": "#182028",
        border: "#232C36",
        ink: "#E6EDF3",         // texto primário
        "ink-muted": "#7C8B99", // texto secundário
        trace: "#4FD8E8",       // accent primário (telemetria/ativo)
        amber: "#FFB020",       // alerta
        success: "#39D98A",     // sucesso
        danger: "#FF5B5B",      // perigo/crítico
      },
      fontFamily: {
        // Nota: em produção, self-hosted via next/font/local (arquivos
        // .woff2 versionados no repo) — não usamos next/font/google aqui
        // de propósito, para não depender de uma chamada de rede externa
        // durante o build.
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        lg: "10px",
      },
    },
  },
  plugins: [],
};
