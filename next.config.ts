import type { NextConfig } from 'next';
const config: NextConfig = {
  turbopack: { root: process.cwd() },
  distDir: process.env.BMWPM_VERIFY_BUILD === '1' ? '.next-verify' : '.next',
  experimental: { proxyClientMaxBodySize: '42mb' },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.BMWPM_API_URL || 'http://127.0.0.1:8001'}/api/:path*` }];
  },
};
export default config;
