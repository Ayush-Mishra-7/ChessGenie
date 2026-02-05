import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import ApiKeyManager from '@/components/ApiKeyManager'
import AnalysisStarter from '@/components/AnalysisStarter'
import AnalysisResults from '@/components/AnalysisResults'

export default async function DashboardPage() {
  const cookie = headers().get('cookie') || ''

  const base = process.env.NEXTAUTH_URL || process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000'
  const url = `${base.replace(/\/$/, '')}/api/auth/me`

  const res = await fetch(url, {
    headers: { cookie },
    cache: 'no-store'
  })

  const data = await res.json()

  if (!data?.user) {
    redirect('/login')
  }

  const user = data.user

  return (
    <div className="container mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold mb-4">Chess Analysis Dashboard</h1>
      <p className="text-gray-700 mb-6">Welcome, {user.name ?? user.email}!</p>

      {/* Top Row: Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* API Key Management */}
        <div className="lg:col-span-1">
          <ApiKeyManager />
        </div>

        {/* Analysis Starter */}
        <div className="lg:col-span-1">
          <AnalysisStarter />
        </div>

        {/* Subscription */}
        <div className="lg:col-span-1">
          <div className="bg-white p-6 rounded shadow">
            <h2 className="text-xl font-semibold mb-2">💎 Subscription</h2>
            <p className="text-sm text-gray-600 mb-4">Free tier: 10 games per analysis</p>
            <button className="w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white py-2 px-4 rounded font-medium hover:from-purple-600 hover:to-pink-600">
              Upgrade to Pro - $30/month
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Row: Results */}
      <div className="grid grid-cols-1 gap-6">
        <AnalysisResults />
      </div>
    </div>
  )
}
