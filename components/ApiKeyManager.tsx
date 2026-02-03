"use client"

import { useEffect, useState } from 'react'

type Key = {
  id: string
  platform: string
  username: string
  isValid: boolean
  lastChecked: string
}

export default function ApiKeyManager() {
  const [keys, setKeys] = useState<Key[]>([])
  const [platform, setPlatform] = useState<'LICHESS' | 'CHESS_COM'>('LICHESS')
  const [username, setUsername] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadKeys() {
    const res = await fetch('/api/apikeys')
    const data = await res.json()
    if (res.ok) setKeys(data.keys || [])
  }

  useEffect(() => {
    loadKeys()
  }, [])

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const res = await fetch('/api/apikeys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, username, apiKey })
      })

      const data = await res.json()
      if (!res.ok) {
        setError(data.error || 'Failed to add')
      } else {
        setUsername('')
        setApiKey('')
        await loadKeys()
      }
    } catch (e) {
      setError('Network error')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Remove this API key?')) return
    await fetch('/api/apikeys', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) })
    await loadKeys()
  }

  return (
    <div className="bg-white p-6 rounded shadow">
      <h3 className="text-lg font-semibold mb-3">API Keys</h3>

      <form onSubmit={handleAdd} className="grid grid-cols-1 gap-3 mb-4">
        <div>
          <label className="block text-sm mb-1">Platform</label>
          <select value={platform} onChange={e => setPlatform(e.target.value as any)} className="w-full border px-2 py-1 rounded">
            <option value="LICHESS">Lichess</option>
            <option value="CHESS_COM">Chess.com</option>
          </select>
        </div>

        <div>
          <label className="block text-sm mb-1">Username</label>
          <input value={username} onChange={e => setUsername(e.target.value)} className="w-full border px-2 py-1 rounded" />
        </div>

        <div>
          <label className="block text-sm mb-1">API Key / Token</label>
          <input value={apiKey} onChange={e => setApiKey(e.target.value)} className="w-full border px-2 py-1 rounded" />
        </div>

        {error && <div className="text-red-600">{error}</div>}

        <div>
          <button disabled={loading} className="bg-blue-600 text-white px-4 py-2 rounded">
            {loading ? 'Adding…' : 'Add API Key'}
          </button>
        </div>
      </form>

      <div>
        {keys.length === 0 ? (
          <div className="text-sm text-gray-600">No API keys added.</div>
        ) : (
          <ul className="space-y-2">
            {keys.map(k => (
              <li key={k.id} className="flex items-center justify-between border p-2 rounded">
                <div>
                  <div className="font-medium">{k.platform} — {k.username}</div>
                  <div className="text-xs text-gray-500">{k.isValid ? 'Valid' : 'Invalid'} — Last checked: {new Date(k.lastChecked).toLocaleString()}</div>
                </div>
                <div>
                  <button onClick={() => handleDelete(k.id)} className="text-sm text-red-600">Remove</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
