import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { ClerkProvider } from '@clerk/nextjs'
import './globals.css'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  title: 'Case Agent',
  description: 'AI-powered legal research assistant',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en" className={inter.variable}>
        <body className="bg-[#0d0d0d] text-[#e8e8e8] h-screen overflow-hidden">
          {children}
        </body>
      </html>
    </ClerkProvider>
  )
}
