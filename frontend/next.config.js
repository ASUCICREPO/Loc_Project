/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true
  },
  // Environment variables for API endpoints
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
    NEXT_PUBLIC_CHAT_ENDPOINT: process.env.NEXT_PUBLIC_CHAT_ENDPOINT,
  }
}

module.exports = nextConfig