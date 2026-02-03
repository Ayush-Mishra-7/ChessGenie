import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import ApiKeyManager from '@/components/ApiKeyManager'

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
      <h1 className="text-3xl font-bold mb-4">Dashboard</h1>
      <p className="text-gray-700 mb-6">Welcome, {user.name ?? user.email} — this is your dashboard.</p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ApiKeyManager />
        </div>

        <div>
          <div className="bg-white p-6 rounded shadow">
            <h2 className="text-xl font-semibold mb-2">Subscription</h2>
            <p className="text-sm text-gray-600">Manage your subscription and usage limits here.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
