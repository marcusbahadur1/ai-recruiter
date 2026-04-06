import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AI Recruiter',
  description: 'AI-powered recruitment automation',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return children
}
