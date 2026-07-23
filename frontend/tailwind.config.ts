import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#211914",
        walnut: "#6f4428",
        cedar: "#9f6a3d",
        parchment: "#f4ead9",
        vellum: "#fbf6ec",
        brass: "#c79a44",
        moss: "#66785f",
        teal: "#2f6f6b",
        oxblood: "#7d2f2f",
        line: "#dfd0b8",
        shadowwood: "#120d0a"
      },
      boxShadow: {
        library: "0 24px 80px rgba(40, 25, 14, 0.16)",
        insetShelf: "inset 0 -18px 24px rgba(83, 48, 22, 0.16)"
      },
      borderRadius: {
        panel: "8px"
      }
    }
  },
  plugins: []
};

export default config;
