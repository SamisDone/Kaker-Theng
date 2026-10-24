import path from "node:path";
import type { NextConfig } from "next";

// On Cloudflare Pages (CF_PAGES=1), refuse to build a site that can't
// reach its API.
if (process.env.CF_PAGES && !process.env.NEXT_PUBLIC_API_URL) {
  throw new Error("Set NEXT_PUBLIC_API_URL (the Render URL) in the Pages project's environment variables.");
}

const nextConfig: NextConfig = {
  // A static site: no API routes, server actions or middleware. All the
  // work happens in the Python backend at NEXT_PUBLIC_API_URL.
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  turbopack: { root: path.resolve(__dirname) },
};

export default nextConfig;
