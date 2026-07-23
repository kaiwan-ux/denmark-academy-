const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/books/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=86400, s-maxage=604800, stale-while-revalidate=2592000" },
          { key: "Accept-Ranges", value: "bytes" }
        ]
      }
    ];
  },
  turbopack: {
    root: path.resolve(__dirname)
  }
};

module.exports = nextConfig;