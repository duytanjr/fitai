import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for optimised Docker image (copies only needed files)
  output: "standalone",

  // Disable Turbopack for production build — fixes route group discovery bug in Next.js 16
  bundlePagesRouterDependencies: true,

  // Proxy /api/* → FastAPI backend (avoids CORS in production)
  async rewrites() {
    return [
      {
        // Proxy /api/v1/* → FastAPI backend container (Docker internal network)
        // Trình duyệt gọi localhost:3000/api/v1/... 
        // → Next.js server forward sang backend:8000/api/v1/... (mạng nội bộ Docker)
        source: "/api/:path*",
        destination: "http://backend:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
