import createNextIntlPlugin from 'next-intl/plugin'
const withNextIntl = createNextIntlPlugin('./i18n/request.ts')

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output for Docker/Fly.io deployment.
  // Produces a self-contained server in .next/standalone with only server-side deps.
  output: 'standalone',

  async rewrites() {
    // NEXT_PUBLIC_API_URL can be overridden via Docker --build-arg at deploy time.
    // Falls back to the Fly.io API URL.
    const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? '').trim() || 'https://airecruiterz-api.fly.dev'
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiUrl}/api/v1/:path*`,
      },
    ]
  },
}
export default withNextIntl(nextConfig)
