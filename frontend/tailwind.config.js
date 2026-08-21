/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Futuristic palette: deep space + electric cyan/violet accents.
        space: {
          900: "#05060f",
          800: "#0a0c1b",
          700: "#11142b",
          600: "#1a1f3d",
        },
        neon: {
          cyan: "#22d3ee",
          violet: "#a855f7",
          pink: "#ec4899",
          blue: "#3b82f6",
        },
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 40px rgba(34, 211, 238, 0.35)",
        "glow-violet": "0 0 50px rgba(168, 85, 247, 0.45)",
      },
      keyframes: {
        float: {
          "0%,100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-8px)" },
        },
        pulseGlow: {
          "0%,100%": { opacity: "0.7" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        float: "float 4s ease-in-out infinite",
        pulseGlow: "pulseGlow 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
