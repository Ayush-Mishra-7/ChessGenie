"use client"

import { useEffect, useState, useCallback } from 'react'
import dynamic from 'next/dynamic'

// Dynamic import to avoid SSR issues with react-chessboard
const PositionViewer = dynamic(() => import('./PositionViewer'), { ssr: false })
const GameViewer = dynamic(() => import('./GameViewer'), { ssr: false })

type GameResult = {
    game_id: string
    white: string
    black: string
    result: string
    opening?: string
    status: string
    accuracy_white?: number
    accuracy_black?: number
    platform?: string
    date?: string
    mistakes?: Array<{
        move_number: number
        player: string
        played: string
        best: string
        loss: number
        fen?: string
        played_uci?: string
        best_uci?: string
    }>
    blunders?: Array<{
        move_number: number
        player: string
        played: string
        best: string
        loss: number
        fen?: string
        played_uci?: string
        best_uci?: string
    }>
}

type AnalysisGame = {
    id: string
    gameId: string
    jobId?: string
    pgn: string
    result: GameResult
    createdAt: string
}

type JobSummary = {
    id: string
    status: string
    createdAt: string
    payload: { platform?: string, username?: string }
    gameCount: number
}

export default function AnalysisResults() {
    const [games, setGames] = useState<AnalysisGame[]>([])
    const [jobs, setJobs] = useState<JobSummary[]>([])
    const [loading, setLoading] = useState(true)
    const [expandedJob, setExpandedJob] = useState<string | null>(null)
    const [expandedGame, setExpandedGame] = useState<string | null>(null)
    const [isPolling, setIsPolling] = useState(false)
    const [lastGameCount, setLastGameCount] = useState(0)
    const [newGamesCount, setNewGamesCount] = useState(0)
    const [usernames, setUsernames] = useState<string[]>([]) // User's profile names
    const [selectedPosition, setSelectedPosition] = useState<{
        fen: string,
        played: string,
        best: string,
        orientation: 'white' | 'black',
        whitePlayer?: string,
        blackPlayer?: string
    } | null>(null)
    const [reviewGame, setReviewGame] = useState<AnalysisGame | null>(null)
    const [jobToDelete, setJobToDelete] = useState<JobSummary | null>(null)


    // Fetch user's profile names from API keys
    useEffect(() => {
        const loadUsernames = async () => {
            try {
                const res = await fetch('/api/apikeys')
                if (res.ok) {
                    const data = await res.json()
                    const names = (data.keys || []).map((k: any) => k.username.toLowerCase())
                    setUsernames(names)
                }
            } catch (e) {
                console.error('Failed to load usernames', e)
            }
        }
        loadUsernames()
    }, [])

    const loadGames = useCallback(async (silent = false) => {
        try {
            if (!silent) setLoading(true)
            const res = await fetch('/api/analysis/games')
            if (res.ok) {
                const data = await res.json()
                const newGames = data.games || []
                const jobSummaries = data.jobs || []

                // Check if we got new games
                if (newGames.length > lastGameCount && lastGameCount > 0) {
                    setNewGamesCount(newGames.length - lastGameCount)
                    // Auto-clear the "new games" indicator after 3 seconds
                    setTimeout(() => setNewGamesCount(0), 3000)
                }

                setGames(newGames)
                setJobs(jobSummaries)
                setLastGameCount(newGames.length)
            }
        } catch (e) {
            console.error('Failed to load games', e)
        } finally {
            if (!silent) setLoading(false)
        }
    }, [lastGameCount])
    const deleteJob = async (jobId: string) => {
        try {
            const res = await fetch(`/api/analysis/jobs/${jobId}`, {
                method: 'DELETE'
            })

            if (res.ok) {
                // Remove job and its games from local state
                setJobs(prev => prev.filter(j => j.id !== jobId))
                setGames(prev => prev.filter(g => g.jobId !== jobId))
            } else {
                alert('Failed to delete analysis')
            }
        } catch (e) {
            console.error('Delete failed', e)
            alert('Error deleting analysis')
        }
    }

    const deleteGame = async (id: string) => {
        try {
            const res = await fetch(`/api/analysis/games/${id}`, {
                method: 'DELETE'
            })

            if (res.ok) {
                // Remove from local state
                setGames(prev => prev.filter(g => g.id !== id))
            } else {
                alert('Failed to delete analysis')
            }
        } catch (e) {
            console.error('Delete failed', e)
            alert('Error deleting analysis')
        }
    }

    // Initial load
    useEffect(() => {
        loadGames()
    }, [])

    // Polling for live updates - check for running jobs
    useEffect(() => {
        const checkAndPoll = async () => {
            try {
                const res = await fetch('/api/analysis/jobs')
                if (res.ok) {
                    const data = await res.json()
                    const hasRunningJob = data.jobs?.some(
                        (j: any) => j.status === 'RUNNING' || j.status === 'QUEUED'
                    )
                    setIsPolling(hasRunningJob)
                }
            } catch (e) {
                // Ignore errors
            }
        }

        checkAndPoll()
        const statusInterval = setInterval(checkAndPoll, 5000)
        return () => clearInterval(statusInterval)
    }, [])

    // Poll for games while analysis is running
    useEffect(() => {
        if (!isPolling) return

        const pollInterval = setInterval(() => {
            loadGames(true) // Silent load (no loading spinner)
        }, 3000) // Poll every 3 seconds

        return () => clearInterval(pollInterval)
    }, [isPolling, loadGames])

    const getAccuracyColor = (accuracy?: number) => {
        if (!accuracy) return 'text-gray-500'
        if (accuracy >= 90) return 'text-green-600'
        if (accuracy >= 75) return 'text-blue-600'
        if (accuracy >= 60) return 'text-yellow-600'
        return 'text-red-600'
    }

    const getAccuracyLabel = (accuracy?: number) => {
        if (!accuracy) return 'N/A'
        if (accuracy >= 95) return 'Brilliant!'
        if (accuracy >= 90) return 'Excellent'
        if (accuracy >= 80) return 'Good'
        if (accuracy >= 70) return 'Fair'
        if (accuracy >= 60) return 'Inaccurate'
        return 'Poor'
    }

    // Determine personalized win/loss/draw based on user's profile name
    const getResultTag = (result: string, white: string, black: string) => {
        const isUserWhite = usernames.some(u => white.toLowerCase().includes(u))
        const isUserBlack = usernames.some(u => black.toLowerCase().includes(u))

        if (result === '1/2-1/2' || result === '½-½') {
            return { label: 'Draw', bgColor: 'bg-gray-100', textColor: 'text-gray-700', icon: '🤝' }
        }

        if (result === '1-0') {
            // White won
            if (isUserWhite) {
                return { label: 'You Won', bgColor: 'bg-green-100', textColor: 'text-green-700', icon: '🏆' }
            } else if (isUserBlack) {
                return { label: 'You Lost', bgColor: 'bg-red-100', textColor: 'text-red-700', icon: '😔' }
            }
            return { label: 'White Won', bgColor: 'bg-blue-100', textColor: 'text-blue-700', icon: '👑' }
        }

        if (result === '0-1') {
            // Black won
            if (isUserBlack) {
                return { label: 'You Won', bgColor: 'bg-green-100', textColor: 'text-green-700', icon: '🏆' }
            } else if (isUserWhite) {
                return { label: 'You Lost', bgColor: 'bg-red-100', textColor: 'text-red-700', icon: '😔' }
            }
            return { label: 'Black Won', bgColor: 'bg-blue-100', textColor: 'text-blue-700', icon: '👑' }
        }

        return { label: result, bgColor: 'bg-gray-100', textColor: 'text-gray-600', icon: '' }
    }

    if (loading) {
        return (
            <div className="bg-white p-6 rounded shadow">
                <h3 className="text-lg font-semibold mb-4">📈 Analysis Results</h3>
                <div className="text-gray-500">Loading games...</div>
            </div>
        )
    }

    if (games.length === 0) {
        return (
            <div className="bg-white p-6 rounded shadow">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold">📈 Analysis Results</h3>
                    {isPolling && (
                        <div className="flex items-center gap-2 text-blue-600 text-sm">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                            </span>
                            Analyzing...
                        </div>
                    )}
                </div>
                <div className="text-gray-500 text-sm">
                    {isPolling
                        ? "Games will appear here as they are analyzed..."
                        : "No analyzed games yet. Start an analysis to see your results here!"
                    }
                </div>
            </div>
        )
    }

    return (
        <div className="bg-white p-6 rounded shadow">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">📈 Analysis Results</h3>
                <div className="flex items-center gap-3">
                    {newGamesCount > 0 && (
                        <span className="bg-green-100 text-green-700 text-xs font-medium px-2 py-1 rounded animate-pulse">
                            +{newGamesCount} new
                        </span>
                    )}
                    {isPolling && (
                        <div className="flex items-center gap-2 text-blue-600 text-sm">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                            </span>
                            Live
                        </div>
                    )}
                    <span className="text-sm text-gray-500">{games.length} games</span>
                </div>
            </div>

            {/* Jobs list - click to expand and see games */}
            <div className="space-y-3">
                {jobs.length > 0 ? (
                    jobs.map(job => {
                        const isJobExpanded = expandedJob === job.id
                        const jobGames = games.filter(g => g.jobId === job.id)
                        const jobDate = new Date(job.createdAt).toLocaleDateString()
                        const platform = job.payload?.platform || 'Unknown'
                        const username = job.payload?.username || ''

                        return (
                            <div key={job.id} className="border rounded-lg overflow-hidden">
                                {/* Job Header - Click to expand */}
                                <div
                                    className={`p-3 cursor-pointer hover:bg-gray-50 flex items-center justify-between ${isJobExpanded ? 'bg-blue-50 border-b' : ''}`}
                                    onClick={() => setExpandedJob(isJobExpanded ? null : job.id)}
                                >
                                    <div className="flex items-center gap-3">
                                        <span className="text-2xl">
                                            {platform === 'LICHESS' ? '🦁' : platform === 'CHESSCOM' ? '♟️' : '📊'}
                                        </span>
                                        <div>
                                            <div className="font-medium">
                                                {username} • {jobGames.length} games
                                            </div>
                                            <div className="text-xs text-gray-500">
                                                {jobDate} • {job.status === 'COMPLETED' ? '✅ Complete' : job.status === 'RUNNING' ? '⏳ Running' : job.status}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setJobToDelete(job)
                                            }}
                                            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                                            title="Delete Analysis Session"
                                        >
                                            🗑️
                                        </button>
                                        <span className={`text-gray-400 transition-transform ${isJobExpanded ? 'rotate-180' : ''}`}>
                                            ▼
                                        </span>
                                    </div>
                                </div>

                                {/* Expanded Job - Show Games */}
                                {isJobExpanded && (
                                    <div className="p-3 bg-gray-50 space-y-2">
                                        {jobGames.length === 0 ? (
                                            <div className="text-sm text-gray-500 text-center py-3">
                                                No games in this analysis yet...
                                            </div>
                                        ) : (
                                            jobGames.map(game => {
                                                const r = game.result
                                                const isExpanded = expandedGame === game.id
                                                const isAnalyzed = r.status === 'analyzed'

                                                return (
                                                    <div key={game.id} className="bg-white border rounded-lg overflow-hidden">
                                                        {/* Game Header */}
                                                        <div
                                                            className="p-3 cursor-pointer hover:bg-gray-50 flex items-center justify-between"
                                                            onClick={() => setExpandedGame(isExpanded ? null : game.id)}
                                                        >
                                                            <div className="flex-1 min-w-0">
                                                                <div className="font-medium flex items-center gap-2">
                                                                    {r.white} vs {r.black}
                                                                    {(() => {
                                                                        const tag = getResultTag(r.result, r.white, r.black)
                                                                        return (
                                                                            <span className={`text-xs px-1.5 py-0.5 rounded ${tag.bgColor} ${tag.textColor}`}>
                                                                                {tag.icon} {tag.label}
                                                                            </span>
                                                                        )
                                                                    })()}
                                                                </div>
                                                                <div className="text-xs text-gray-500 truncate">
                                                                    {r.opening || 'Unknown opening'}
                                                                </div>
                                                            </div>

                                                            {isAnalyzed ? (
                                                                <div className="flex items-center gap-3">
                                                                    <div className="text-right">
                                                                        <div className={`font-bold ${getAccuracyColor(r.accuracy_white)}`}>
                                                                            {r.accuracy_white?.toFixed(1)}%
                                                                        </div>
                                                                        <div className="text-xs text-gray-500">White</div>
                                                                    </div>
                                                                    <div className="text-right">
                                                                        <div className={`font-bold ${getAccuracyColor(r.accuracy_black)}`}>
                                                                            {r.accuracy_black?.toFixed(1)}%
                                                                        </div>
                                                                        <div className="text-xs text-gray-500">Black</div>
                                                                    </div>
                                                                </div>
                                                            ) : (
                                                                <span className="text-xs text-yellow-600 bg-yellow-100 px-2 py-1 rounded">
                                                                    Pending
                                                                </span>
                                                            )}
                                                        </div>

                                                        {/* Expanded Details */}
                                                        {isExpanded && isAnalyzed && (
                                                            <div className="border-t p-3 bg-gray-50">
                                                                <div className="flex justify-between items-start mb-3">
                                                                    <div className="grid grid-cols-2 gap-4">
                                                                        <div className="text-center p-2 bg-white rounded border">
                                                                            <div className={`text-2xl font-bold ${getAccuracyColor(r.accuracy_white)}`}>
                                                                                {r.accuracy_white?.toFixed(1)}%
                                                                            </div>
                                                                            <div className="text-xs text-gray-500">
                                                                                {r.white} - {getAccuracyLabel(r.accuracy_white)}
                                                                            </div>
                                                                        </div>
                                                                        <div className="text-center p-2 bg-white rounded border">
                                                                            <div className={`text-2xl font-bold ${getAccuracyColor(r.accuracy_black)}`}>
                                                                                {r.accuracy_black?.toFixed(1)}%
                                                                            </div>
                                                                            <div className="text-xs text-gray-500">
                                                                                {r.black} - {getAccuracyLabel(r.accuracy_black)}
                                                                            </div>
                                                                        </div>
                                                                    </div>

                                                                    <button
                                                                        onClick={() => setReviewGame(game)}
                                                                        className="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700 font-medium text-sm flex items-center gap-2"
                                                                    >
                                                                        <span>♟️</span> Review Game
                                                                    </button>
                                                                </div>

                                                                {/* Blunders */}
                                                                {r.blunders && r.blunders.length > 0 && (
                                                                    <div className="mb-2">
                                                                        <div className="text-sm font-medium text-red-600 mb-1">
                                                                            💥 Blunders ({r.blunders.length})
                                                                        </div>
                                                                        <div className="text-xs space-y-1">
                                                                            {r.blunders.slice(0, 5).map((b, i) => (
                                                                                <div
                                                                                    key={i}
                                                                                    className={`bg-red-50 p-2 rounded ${b.fen ? 'cursor-pointer hover:bg-red-100 transition-colors' : ''}`}
                                                                                    onClick={() => {
                                                                                        if (b.fen) {
                                                                                            const isUserBlack = usernames.some(u => r.black.toLowerCase().includes(u))
                                                                                            setSelectedPosition({
                                                                                                fen: b.fen,
                                                                                                played: b.played,
                                                                                                best: b.best,
                                                                                                orientation: isUserBlack ? 'black' : 'white',
                                                                                                whitePlayer: r.white,
                                                                                                blackPlayer: r.black
                                                                                            })
                                                                                        }
                                                                                    }}
                                                                                >
                                                                                    <span className="font-medium">Move {b.move_number}:</span> {b.player} played <span className="font-mono bg-red-100 px-1 rounded">{b.played}</span>
                                                                                    {' '}→ best: <span className="font-mono bg-green-100 px-1 rounded">{b.best}</span>
                                                                                    {b.fen && <span className="ml-2 text-blue-600">🔍 View</span>}
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    </div>
                                                                )}

                                                                {/* Mistakes */}
                                                                {r.mistakes && r.mistakes.length > 0 && (
                                                                    <div>
                                                                        <div className="text-sm font-medium text-yellow-600 mb-1">
                                                                            ⚠️ Mistakes ({r.mistakes.length})
                                                                        </div>
                                                                        <div className="text-xs space-y-1">
                                                                            {r.mistakes.slice(0, 5).map((m, i) => (
                                                                                <div
                                                                                    key={i}
                                                                                    className={`bg-yellow-50 p-2 rounded ${m.fen ? 'cursor-pointer hover:bg-yellow-100 transition-colors' : ''}`}
                                                                                    onClick={() => {
                                                                                        if (m.fen) {
                                                                                            const isUserBlack = usernames.some(u => r.black.toLowerCase().includes(u))
                                                                                            setSelectedPosition({
                                                                                                fen: m.fen,
                                                                                                played: m.played,
                                                                                                best: m.best,
                                                                                                orientation: isUserBlack ? 'black' : 'white',
                                                                                                whitePlayer: r.white,
                                                                                                blackPlayer: r.black
                                                                                            })
                                                                                        }
                                                                                    }}
                                                                                >
                                                                                    <span className="font-medium">Move {m.move_number}:</span> {m.player} played <span className="font-mono bg-yellow-100 px-1 rounded">{m.played}</span>
                                                                                    {' '}→ best: <span className="font-mono bg-green-100 px-1 rounded">{m.best}</span>
                                                                                    {m.fen && <span className="ml-2 text-blue-600">🔍 View</span>}
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                )
                                            })
                                        )}
                                    </div>
                                )}
                            </div>
                        )
                    })
                ) : (
                    <div className="text-center text-gray-500 py-4">
                        No analyses found. Start an analysis to see your results here!
                    </div>
                )}
            </div>

            {/* Position Viewer Modal */}
            {selectedPosition && (
                <PositionViewer
                    fen={selectedPosition.fen}
                    playedMove={selectedPosition.played}
                    bestMove={selectedPosition.best}
                    onClose={() => setSelectedPosition(null)}
                    orientation={selectedPosition.orientation}
                    whitePlayer={selectedPosition.whitePlayer}
                    blackPlayer={selectedPosition.blackPlayer}
                />
            )}

            {/* Game Viewer Modal */}
            {reviewGame && (
                <GameViewer
                    pgn={reviewGame.pgn}
                    onClose={() => setReviewGame(null)}
                    orientation={(() => {
                        const r = reviewGame.result
                        const isUserBlack = usernames.some(u => r.black.toLowerCase().includes(u))
                        return isUserBlack ? 'black' : 'white'
                    })()}
                />
            )}

            {/* Delete Confirmation Modal */}
            {jobToDelete && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-lg shadow-xl max-w-sm w-full p-6 transform transition-all">
                        <div className="text-center">
                            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 mb-4">
                                <span className="text-2xl">🗑️</span>
                            </div>
                            <h3 className="text-lg font-medium text-gray-900 mb-2">Delete Analysis Session?</h3>
                            <p className="text-sm text-gray-500 mb-6">
                                Are you sure you want to delete this session? This will remove
                                <span className="font-bold text-gray-700"> {jobToDelete.gameCount} games </span>
                                and cannot be undone.
                            </p>
                            <div className="flex justify-center gap-3">
                                <button
                                    onClick={() => setJobToDelete(null)}
                                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-lg font-medium transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={() => {
                                        deleteJob(jobToDelete.id)
                                        setJobToDelete(null)
                                    }}
                                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium shadow-sm transition-colors"
                                >
                                    Yes, Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
