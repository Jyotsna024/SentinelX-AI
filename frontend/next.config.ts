import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Allow images from any domain (for future avatar usage if needed)
  images: {
    domains: [],
  },
};

export default nextConfig;
