import type { Metadata } from 'next';
import './globals.css';
import '../components/document-rag.css';
import '../components/reviews-comments.css';
import './premium-theme.css';
import './rag-theme.css';
import './handover-panels.css';
export const metadata:Metadata={title:'BMW | Product Intelligence',description:'Evidence, requirements and product decisions. Local BMW PM demonstration.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>;}
