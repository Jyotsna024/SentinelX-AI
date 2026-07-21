/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        bg: {
          DEFAULT: "var(--bg)",
          card: "var(--card)",
          hover: "var(--card-hover)",
        },
        border: {
          DEFAULT: "var(--border)",
          subtle: "var(--border-subtle)",
        },
        text: {
          DEFAULT: "var(--text)",
          muted: "var(--text-muted)",
          faint: "var(--text-faint)",
        },
        danger: {
          DEFAULT: "var(--danger)",
          muted: "var(--danger-muted)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          muted: "var(--warning-muted)",
        },
        success: {
          DEFAULT: "var(--success)",
          muted: "var(--success-muted)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          muted: "var(--accent-muted)",
        },
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "glow-danger": "glowDanger 2s ease-in-out infinite",
        "glow-warning": "glowWarning 2s ease-in-out infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-in": "slideIn 0.25s ease-out",
      },
      keyframes: {
        glowDanger: {
          "0%, 100%": { boxShadow: "0 0 8px 2px var(--danger-muted)" },
          "50%": { boxShadow: "0 0 20px 6px var(--danger)" },
        },
        glowWarning: {
          "0%, 100%": { boxShadow: "0 0 8px 2px var(--warning-muted)" },
          "50%": { boxShadow: "0 0 20px 6px var(--warning)" },
        },
        fadeIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        slideIn: {
          from: { opacity: "0", transform: "translateX(-12px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
      },
    },
  },
  plugins: [],
};
