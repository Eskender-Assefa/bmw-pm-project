import type { NextConfig } from 'next';
const portable = process.env.BMWPM_WINDOWS_EXPORT === '1';
const config: NextConfig = {
  ...(portable ? { output: 'export' as const, images: { unoptimized: true } } : {}),
  turbopack: { root: process.cwd() },
  distDir: portable ? '.windows-web' : process.env.BMWPM_VERIFY_BUILD === '1' ? '.next-verify' : '.next',
  experimental: { proxyClientMaxBodySize: '42mb' },
  ...(portable ? {} : {
    async rewrites() {
      return [{ source: '/api/:path*', destination: `${process.env.BMWPM_API_URL || 'http://127.0.0.1:8001'}/api/:path*` }];
    },
  }),
};
export default config;
