/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    if (process.env.NODE_ENV === 'development') {
      return [
        { source: '/api/:path*', destination: 'http://localhost:7860/api/:path*' },
        { source: '/download/:path*', destination: 'http://localhost:7860/download/:path*' },
        { source: '/health', destination: 'http://localhost:7860/health' },
      ]
    }
    return []
  },
}

export default nextConfig
