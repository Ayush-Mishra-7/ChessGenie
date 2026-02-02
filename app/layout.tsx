import './globals.css'

export const metadata = {
  title: 'ChessGenie',
  description: 'Chess analysis platform - minimal dev skeleton'
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main className="min-h-screen bg-gray-50 text-gray-900">{children}</main>
      </body>
    </html>
  )
}
