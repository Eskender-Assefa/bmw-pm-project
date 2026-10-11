import type { Metadata } from 'next';
import './globals.css';
export const metadata:Metadata={title:'BMW | Product Intelligence',description:'Evidence, requirements and product decisions. Local BMW PM demonstration.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>;}
