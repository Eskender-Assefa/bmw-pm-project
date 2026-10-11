import type { NextConfig } from 'next';
const config: NextConfig = {
  // Separate build output keeps verification from overwriting a running dev server.
  distDir: process.env.BMWPM_VERIFY_BUILD === '1' ? '.next-verify' : '.next',
  experimental: { proxyClientMaxBodySize: '42mb' },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.BMWPM_API_URL || 'http://127.0.0.1:8000'}/api/:path*` }];
  },
};
export default config;
