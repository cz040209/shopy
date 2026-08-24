import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [{ protocol: "https", hostname: "images.unsplash.com" }],
  },
  allowedDevOrigins: [
    "evening-merger-accessed-basement.trycloudflare.com",
    "127.0.0.1",
    "localhost",
    "192.168.0.20",
  ],
};

export default nextConfig;
