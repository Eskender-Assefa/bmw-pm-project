import type { NextConfig } from 'next';
const config: NextConfig = {
  turbopack: { root: process.cwd() },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.BMWPM_API_URL || 'http://127.0.0.1:8001'}/api/:path*` }];
  },
};
export default config;
