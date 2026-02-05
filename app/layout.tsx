import './globals.css'
import { Providers } from '@/components/Providers'

export const metadata = {
  title: 'ChessGenie',
  description: 'Chess analysis platform - minimal dev skeleton'
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <main className="min-h-screen bg-gray-50 text-gray-900">{children}</main>
        </Providers>
      </body>
    </html>
  )
}
