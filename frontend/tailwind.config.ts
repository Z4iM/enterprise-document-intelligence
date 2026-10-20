import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#131b31",
        muted: "#67728b",
        primary: "#5c5bf4",
        canvas: "#f7f8fc",
        stroke: "#e6e9f2",
      },
      boxShadow: {
        soft: "0 14px 36px -22px rgba(21,32,62,.24)",
      },
      borderRadius: { xl2: "1.25rem" },
    },
  },
  plugins: [],
} satisfies Config;
