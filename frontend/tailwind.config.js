/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0e1512", panel: "#141d19", panel2: "#182420", line: "#25332c",
        cy: "#2dd4bf", vi: "#34d399", ind: "#22d3ee", prism: "#10b981",
        ink: "#e8efeb", dim: "#93a49b", faint: "#68786f",
        ok: "#22c55e", warn: "#f4b860", bad: "#ef4444",
      },
      boxShadow: {
        glow: "0 0 40px -10px rgba(52,211,153,0.45)",
      },
    },
  },
  plugins: [],
};
