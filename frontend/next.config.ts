import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker deploy: copiază doar server-ul minimal în imagine (.next/standalone)
  output: "standalone",
};

export default nextConfig;
