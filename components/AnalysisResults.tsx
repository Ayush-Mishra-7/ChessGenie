"use client"

import { useEffect, useState } from 'react'

type GameResult = {
    game_id: string
    white: string
    black: string
    result: string
    opening?: string
    status: string
    accuracy_white?: number
    accuracy_black?: number
    mistakes?: Array<{
        move_number: number
        player: string
        played: string
        best: string
        loss: number
    }>
    blunders?: Array<{
        move_number: number
        player: string
        played: string
        best: string
        loss: number
    }>
}

type AnalysisGame = {
    id: string
    gameId: string
    result: GameResult
    createdAt: string
}

export default function AnalysisResults() {
    const [games, setGames] = useState<AnalysisGame[]>([])
    const [loading, setLoading] = useState(true)
    const [expandedGame, setExpandedGame] = useState<string | null>(null)

    useEffect(() => {
        loadGames()
    }, [])

    async function loadGames() {
        try {
            const res = await fetch('/api/analysis/games')
            if (res.ok) {
                const data = await res.json()
                setGames(data.games || [])
            }
        } catch (e) {
            console.error('Failed to load games', e)
        } finally {
            setLoading(false)
        }
    }

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
                <h3 className="text-lg font-semibold mb-4">📈 Analysis Results</h3>
                <div className="text-gray-500 text-sm">
                    No analyzed games yet. Start an analysis to see your results here!
                </div>
            </div>
        )
    }

    return (
        <div className="bg-white p-6 rounded shadow">
            <h3 className="text-lg font-semibold mb-4">📈 Analysis Results</h3>

            <div className="space-y-3">
                {games.map(game => {
                    const r = game.result
                    const isExpanded = expandedGame === game.id
                    const isAnalyzed = r.status === 'analyzed'

                    return (
                        <div
                            key={game.id}
                            className="border rounded-lg overflow-hidden"
                        >
                            {/* Game Header */}
                            <div
                                className="p-3 cursor-pointer hover:bg-gray-50 flex items-center justify-between"
                                onClick={() => setExpandedGame(isExpanded ? null : game.id)}
                            >
                                <div>
                                    <div className="font-medium">
                                        {r.white} vs {r.black}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                        {r.opening || 'Unknown opening'} • {r.result}
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
                                    <div className="grid grid-cols-2 gap-4 mb-3">
                                        <div className="text-center p-2 bg-white rounded">
                                            <div className={`text-2xl font-bold ${getAccuracyColor(r.accuracy_white)}`}>
                                                {r.accuracy_white?.toFixed(1)}%
                                            </div>
                                            <div className="text-xs text-gray-500">
                                                {r.white} - {getAccuracyLabel(r.accuracy_white)}
                                            </div>
                                        </div>
                                        <div className="text-center p-2 bg-white rounded">
                                            <div className={`text-2xl font-bold ${getAccuracyColor(r.accuracy_black)}`}>
                                                {r.accuracy_black?.toFixed(1)}%
                                            </div>
                                            <div className="text-xs text-gray-500">
                                                {r.black} - {getAccuracyLabel(r.accuracy_black)}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Blunders */}
                                    {r.blunders && r.blunders.length > 0 && (
                                        <div className="mb-2">
                                            <div className="text-sm font-medium text-red-600 mb-1">
                                                💥 Blunders ({r.blunders.length})
                                            </div>
                                            <div className="text-xs space-y-1">
                                                {r.blunders.slice(0, 3).map((b, i) => (
                                                    <div key={i} className="bg-red-50 p-1 rounded">
                                                        Move {b.move_number}: {b.player} played <span className="font-mono">{b.played}</span>
                                                        {' '}(best: <span className="font-mono">{b.best}</span>)
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
                                                {r.mistakes.slice(0, 3).map((m, i) => (
                                                    <div key={i} className="bg-yellow-50 p-1 rounded">
                                                        Move {m.move_number}: {m.player} played <span className="font-mono">{m.played}</span>
                                                        {' '}(best: <span className="font-mono">{m.best}</span>)
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
