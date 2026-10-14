import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A static site: no API routes, server actions or middleware. All the
  // work happens in the Python backend at NEXT_PUBLIC_API_URL.
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  turbopack: { root: path.resolve(__dirname) },
};

export default nextConfig;
