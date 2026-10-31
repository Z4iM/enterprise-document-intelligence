import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  devIndicators: process.env.EDI_SHOWCASE_MODE === "synthetic-scripted" ? false : undefined,
};

export default nextConfig;
