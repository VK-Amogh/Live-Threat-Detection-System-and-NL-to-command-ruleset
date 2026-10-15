import type { Metadata } from 'next';
export const metadata: Metadata = { title: 'SafeSpace', description: 'Local incident detection and investigation' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
