import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  // No dev badge in screen recordings.
  devIndicators: false,
};

export default nextConfig;
