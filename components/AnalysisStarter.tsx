"use client"

import { useState, useEffect, useRef } from 'react'
import { useToast } from './Toast'

type Job = {
    id: string
    status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED'
    gameCount?: number
    result?: any
    createdAt: string
}

type ApiKey = {
    id: string
    platform: string
    username: string
    isValid: boolean
}

export default function AnalysisStarter() {
    const [keys, setKeys] = useState<ApiKey[]>([])
    const [selectedKey, setSelectedKey] = useState<string>('')
    const [gameLimit, setGameLimit] = useState(10)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [currentJob, setCurrentJob] = useState<Job | null>(null)
    const [recentJobs, setRecentJobs] = useState<Job[]>([])
    const { showToast } = useToast()
    const previousStatus = useRef<string | null>(null)

    // Load API keys on mount
    useEffect(() => {
        loadApiKeys()
        loadRecentJobs()
    }, [])

    // Poll for job status when we have an active job
    useEffect(() => {
        if (!currentJob || currentJob.status === 'COMPLETED' || currentJob.status === 'FAILED') {
            return
        }

        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/analysis/status/${currentJob.id}`)
                if (res.ok) {
                    const data = await res.json()
                    const newStatus = data.status

                    setCurrentJob({
                        id: data.jobId,
                        status: newStatus,
                        gameCount: data.gameCount,
                        result: data.result,
                        createdAt: data.createdAt
                    })

                    // Show toast notification on status change
                    if (previousStatus.current === 'RUNNING' && newStatus === 'COMPLETED') {
                        const gameCount = data.result?.total_games || data.gameCount || 0
                        showToast(`Analysis complete! ${gameCount} games analyzed.`, 'success')
                        loadRecentJobs()
                    } else if (previousStatus.current === 'RUNNING' && newStatus === 'FAILED') {
                        const errorMsg = data.result?.error || 'Unknown error'
                        showToast(`Analysis failed: ${errorMsg}`, 'error')
                        loadRecentJobs()
                    }

                    previousStatus.current = newStatus
                }
            } catch (e) {
                console.error('Failed to poll job status', e)
            }
        }, 2000) // Poll every 2 seconds

        return () => clearInterval(interval)
    }, [currentJob, showToast])

    async function loadApiKeys() {
        try {
            const res = await fetch('/api/apikeys')
            const data = await res.json()
            if (res.ok && data.keys) {
                setKeys(data.keys)
                if (data.keys.length > 0 && !selectedKey) {
                    setSelectedKey(data.keys[0].id)
                }
            }
        } catch (e) {
            console.error('Failed to load API keys', e)
        }
    }

    async function loadRecentJobs() {
        try {
            const res = await fetch('/api/analysis/jobs')
            if (res.ok) {
                const data = await res.json()
                setRecentJobs(data.jobs || [])
            }
        } catch (e) {
            // Endpoint might not exist yet, that's ok
        }
    }

    async function handleStartAnalysis(e: React.FormEvent) {
        e.preventDefault()
        setError(null)
        setLoading(true)

        const key = keys.find(k => k.id === selectedKey)
        if (!key) {
            setError('Please select an API key first')
            setLoading(false)
            return
        }

        try {
            // Step 1: Create job via Next.js API
            const res = await fetch('/api/analysis/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    platform: key.platform,
                    username: key.username,
                    game_limit: gameLimit
                })
            })

            const data = await res.json()
            if (!res.ok) {
                setError(data.error || 'Failed to start analysis')
                setLoading(false)
                return
            }

            const jobId = data.jobId

            // Step 2: Trigger backend processing
            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
            const processRes = await fetch(`${backendUrl}/jobs/${jobId}/process`, {
                method: 'POST'
            })

            if (!processRes.ok) {
                const processData = await processRes.json()
                setError(processData.detail || 'Failed to process job')
                setLoading(false)
                return
            }

            // Step 3: Set current job for polling
            setCurrentJob({
                id: jobId,
                status: 'RUNNING',
                createdAt: new Date().toISOString()
            })

        } catch (e) {
            setError('Network error - make sure the backend server is running')
        } finally {
            setLoading(false)
        }
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'COMPLETED': return 'text-green-600 bg-green-100'
            case 'RUNNING': return 'text-blue-600 bg-blue-100'
            case 'QUEUED': return 'text-yellow-600 bg-yellow-100'
            case 'FAILED': return 'text-red-600 bg-red-100'
            default: return 'text-gray-600 bg-gray-100'
        }
    }

    return (
        <div className="bg-white p-6 rounded shadow">
            <h3 className="text-lg font-semibold mb-4">🎯 Analyze Your Games</h3>

            {keys.length === 0 ? (
                <div className="text-gray-600 text-sm p-4 bg-yellow-50 rounded border border-yellow-200">
                    <p>No API keys found. Add a Lichess or Chess.com account above to start analyzing games.</p>
                </div>
            ) : (
                <form onSubmit={handleStartAnalysis} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">Account to Analyze</label>
                        <select
                            value={selectedKey}
                            onChange={e => setSelectedKey(e.target.value)}
                            className="w-full border px-3 py-2 rounded"
                        >
                            {keys.map(k => (
                                <option key={k.id} value={k.id}>
                                    {k.platform} — {k.username}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-1">
                            Number of Games (max 100)
                        </label>
                        <input
                            type="number"
                            min={1}
                            max={100}
                            value={gameLimit}
                            onChange={e => setGameLimit(Math.min(100, Math.max(1, parseInt(e.target.value) || 10)))}
                            className="w-full border px-3 py-2 rounded"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                            Start with 10 games for testing, scale up later
                        </p>
                    </div>

                    {error && <div className="text-red-600 text-sm">{error}</div>}

                    <button
                        type="submit"
                        disabled={loading || (currentJob?.status === 'RUNNING')}
                        className="w-full bg-blue-600 text-white py-2 px-4 rounded font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                    >
                        {loading ? 'Starting...' : currentJob?.status === 'RUNNING' ? 'Analysis in Progress...' : '🚀 Start Analysis'}
                    </button>
                </form>
            )}

            {/* Current Job Status */}
            {currentJob && (
                <div className="mt-6 p-4 bg-gray-50 rounded border">
                    <h4 className="font-medium mb-2">Current Analysis</h4>
                    <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(currentJob.status)}`}>
                            {currentJob.status}
                        </span>
                        {currentJob.status === 'RUNNING' && (
                            <span className="text-sm text-gray-500">⏳ Fetching games...</span>
                        )}
                        {currentJob.status === 'COMPLETED' && currentJob.gameCount !== undefined && (
                            <span className="text-sm text-green-600">✅ {currentJob.gameCount} games fetched!</span>
                        )}
                        {currentJob.status === 'FAILED' && currentJob.result?.error && (
                            <span className="text-sm text-red-600">❌ {currentJob.result.error}</span>
                        )}
                    </div>
                </div>
            )}

            {/* Recent Jobs */}
            {recentJobs.length > 0 && (
                <div className="mt-6">
                    <h4 className="font-medium mb-2">Recent Analyses</h4>
                    <ul className="space-y-2">
                        {recentJobs.slice(0, 5).map(job => (
                            <li key={job.id} className="flex items-center justify-between text-sm border-b pb-2">
                                <span className="text-gray-600">
                                    {new Date(job.createdAt).toLocaleDateString()}
                                </span>
                                <span className={`px-2 py-1 rounded text-xs ${getStatusColor(job.status)}`}>
                                    {job.status}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    )
}
