import './globals.css';

import { GeistMono } from 'geist/font/mono';
import { GeistSans } from 'geist/font/sans';
import type { Metadata, Viewport } from 'next';
import { Newsreader } from 'next/font/google';
import type { ReactNode } from 'react';

import { Providers } from '@/lib/providers';

const newsreader = Newsreader({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-newsreader',
  weight: ['400', '500', '600'],
});

export const metadata: Metadata = {
  title: {
    default: 'md-converter — EPUB et PDF vers Markdown',
    template: '%s — md-converter',
  },
  description:
    'Conversion locale d’EPUB et de PDF en Markdown propre. 100% sur ta machine.',
  applicationName: 'md-converter',
  authors: [{ name: 'Henluy Soro' }],
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#FAFAF7' },
    { media: '(prefers-color-scheme: dark)', color: '#0F0E0C' },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="fr"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable} ${newsreader.variable}`}
    >
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
