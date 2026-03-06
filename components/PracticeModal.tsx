"use client"

import { useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'

type PracticePosition = {
    fen: string
    correct_move_uci: string
    correct_move_san: string
    difficulty: string
    method: string
    eval_change: number
    motifs?: string[]
}

type PracticeApiResponse = {
    positions?: Array<{
        fen: string
        correct_move_uci?: string
        correct_move_san?: string
        difficulty?: string
        method?: string
        eval_change?: number
        motifs?: string[]
    }>
    generated?: Array<{
        fen: string
        solution_move_uci?: string
        solution_move_san?: string
        difficulty?: string
        generation_method?: string
        eval_gap_cp?: number
        motifs?: string[]
    }>
}

function normalizePracticePositions(data: PracticeApiResponse): PracticePosition[] {
    const legacyPositions = data.positions || []
    if (legacyPositions.length > 0) {
        return legacyPositions.map(position => ({
            fen: position.fen,
            correct_move_uci: position.correct_move_uci || '',
            correct_move_san: position.correct_move_san || '',
            difficulty: position.difficulty || 'medium',
            method: position.method || 'generated',
            eval_change: position.eval_change || 0,
            motifs: position.motifs || []
        }))
    }

    return (data.generated || []).map(position => ({
        fen: position.fen,
        correct_move_uci: position.solution_move_uci || '',
        correct_move_san: position.solution_move_san || '',
        difficulty: position.difficulty || 'medium',
        method: position.generation_method || 'generated',
        eval_change: position.eval_gap_cp || 0,
        motifs: position.motifs || []
    }))
}

type PracticeModalProps = {
    originalFen: string
    playedMove: string
    bestMove: string
    playedUci: string
    bestUci: string
    onClose: () => void
    orientation?: 'white' | 'black'
    whitePlayer?: string
    blackPlayer?: string
}

export default function PracticeModal({
    originalFen,
    playedMove,
    bestMove,
    playedUci,
    bestUci,
    onClose,
    orientation = 'white',
    whitePlayer = 'White',
    blackPlayer = 'Black'
}: PracticeModalProps) {
    const [positions, setPositions] = useState<PracticePosition[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [currentIndex, setCurrentIndex] = useState(0)
    const [showAnswer, setShowAnswer] = useState(false)
    const [showOriginal, setShowOriginal] = useState(true) // Start by showing original

    useEffect(() => {
        const fetchPositions = async () => {
            try {
                setLoading(true)
                setError(null)

                const res = await fetch('/api/analysis/practice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        fen: originalFen,
                        played_uci: playedUci,
                        best_uci: bestUci,
                        count: 10
                    })
                })

                if (!res.ok) {
                    let message = 'Failed to generate practice positions'

                    try {
                        const payload = await res.json()
                        message = payload.error || message
                    } catch {
                        // Ignore JSON parsing failures and use the default message.
                    }

                    throw new Error(message)
                }

                const data: PracticeApiResponse = await res.json()
                const normalizedPositions = normalizePracticePositions(data)

                setPositions(normalizedPositions)
                setCurrentIndex(0)
                setShowAnswer(false)
                setShowOriginal(normalizedPositions.length === 0)
            } catch (e: any) {
                setError(e.message || 'Something went wrong')
            } finally {
                setLoading(false)
            }
        }

        fetchPositions()
    }, [originalFen, playedUci, bestUci])

    const currentPosition = positions[currentIndex]

    const goTo = (index: number) => {
        setCurrentIndex(index)
        setShowAnswer(false)
        setShowOriginal(false)
    }

    const getDifficultyBadge = (difficulty: string) => {
        switch (difficulty) {
            case 'easy':
                return { bg: 'bg-green-100', text: 'text-green-700', label: '🟢 Easy' }
            case 'medium':
                return { bg: 'bg-yellow-100', text: 'text-yellow-700', label: '🟡 Medium' }
            case 'hard':
                return { bg: 'bg-red-100', text: 'text-red-700', label: '🔴 Hard' }
            default:
                return { bg: 'bg-gray-100', text: 'text-gray-700', label: '⚪ Unknown' }
        }
    }

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div
                className="bg-white rounded-xl shadow-2xl max-w-lg w-full overflow-hidden max-h-[90vh] flex flex-col"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="bg-gradient-to-r from-purple-700 to-indigo-700 text-white p-4 flex items-center justify-between flex-shrink-0">
                    <div>
                        <h3 className="font-semibold text-lg">🎯 Practice Mode</h3>
                        <p className="text-purple-200 text-xs">
                            Train similar positions to avoid this mistake
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-white/80 hover:text-white text-2xl font-bold leading-none"
                    >
                        ×
                    </button>
                </div>

                {/* Content */}
                <div className="overflow-y-auto flex-1">
                    {loading ? (
                        <div className="p-8 text-center">
                            <div className="inline-block animate-spin rounded-full h-10 w-10 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
                            <p className="text-gray-600 font-medium">Generating practice positions...</p>
                            <p className="text-gray-400 text-sm mt-1">
                                Analyzing tactical patterns with Stockfish
                            </p>
                        </div>
                    ) : error ? (
                        <div className="p-8 text-center">
                            <p className="text-red-600 font-medium">❌ {error}</p>
                            <button
                                onClick={onClose}
                                className="mt-4 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm"
                            >
                                Close
                            </button>
                        </div>
                    ) : (
                        <>
                            {/* Tab bar: Original + positions */}
                            <div className="flex border-b overflow-x-auto flex-shrink-0">
                                <button
                                    onClick={() => { setShowOriginal(true); setShowAnswer(false) }}
                                    className={`px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${showOriginal
                                            ? 'border-purple-600 text-purple-700 bg-purple-50'
                                            : 'border-transparent text-gray-500 hover:text-gray-700'
                                        }`}
                                >
                                    📋 Original
                                </button>
                                {positions.map((pos, i) => {
                                    const badge = getDifficultyBadge(pos.difficulty)
                                    return (
                                        <button
                                            key={i}
                                            onClick={() => goTo(i)}
                                            className={`px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${!showOriginal && currentIndex === i
                                                    ? 'border-purple-600 text-purple-700 bg-purple-50'
                                                    : 'border-transparent text-gray-500 hover:text-gray-700'
                                                }`}
                                        >
                                            #{i + 1}
                                        </button>
                                    )
                                })}
                            </div>

                            {/* Board */}
                            <div className="p-4 bg-gray-100 flex flex-col items-center gap-2">
                                {showOriginal ? (
                                    <>
                                        <div className="text-sm font-medium text-gray-600 mb-1">
                                            Original Mistake Position
                                        </div>
                                        <div className="w-[320px] h-[320px] rounded shadow overflow-hidden">
                                            <Chessboard
                                                key={originalFen}
                                                options={{
                                                    id: "practice-original-board",
                                                    position: originalFen,
                                                    animationDurationInMs: 0,
                                                    allowDragging: false,
                                                    boardOrientation: orientation
                                                }}
                                            />
                                        </div>
                                        <div className="mt-2 grid grid-cols-2 gap-3 w-[320px]">
                                            <div className="bg-white p-2 rounded border border-red-100 shadow-sm text-center">
                                                <div className="text-xs text-gray-500 uppercase font-semibold mb-0.5">Played</div>
                                                <span className="text-red-600 font-bold font-mono">{playedMove}</span>
                                            </div>
                                            <div className="bg-white p-2 rounded border border-green-100 shadow-sm text-center">
                                                <div className="text-xs text-gray-500 uppercase font-semibold mb-0.5">Best</div>
                                                <span className="text-green-600 font-bold font-mono">{bestMove}</span>
                                            </div>
                                        </div>
                                    </>
                                ) : currentPosition ? (
                                    <>
                                        <div className="w-[320px] flex items-center justify-between mb-1">
                                            <span className="text-sm font-medium text-gray-600">
                                                Position {currentIndex + 1} / {positions.length}
                                            </span>
                                            {(() => {
                                                const badge = getDifficultyBadge(currentPosition.difficulty)
                                                return (
                                                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge.bg} ${badge.text}`}>
                                                        {badge.label}
                                                    </span>
                                                )
                                            })()}
                                        </div>
                                        <div className="w-[320px] h-[320px] rounded shadow overflow-hidden">
                                            <Chessboard
                                                key={currentPosition.fen}
                                                options={{
                                                    id: "practice-board",
                                                    position: currentPosition.fen,
                                                    animationDurationInMs: 0,
                                                    allowDragging: false,
                                                    boardOrientation: orientation
                                                }}
                                            />
                                        </div>

                                        {/* Answer section */}
                                        <div className="w-[320px] mt-2">
                                            {showAnswer ? (
                                                <div className="bg-white p-3 rounded-lg border border-green-200 shadow-sm">
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <div className="text-xs text-gray-500 uppercase font-semibold mb-0.5">
                                                                Best Move
                                                            </div>
                                                            <div className="flex items-baseline gap-2">
                                                                <span className="text-green-600 font-bold font-mono text-lg">
                                                                    {currentPosition.correct_move_san}
                                                                </span>
                                                                <span className="text-gray-400 text-xs">
                                                                    ({currentPosition.correct_move_uci})
                                                                </span>
                                                            </div>
                                                        </div>
                                                        <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                                                            +{currentPosition.eval_change}cp
                                                        </span>
                                                    </div>
                                                    
                                                    {/* Motifs Display */}
                                                    {currentPosition.motifs && currentPosition.motifs.length > 0 && (
                                                        <div className="mt-3 pt-2 border-t border-gray-100">
                                                            <div className="text-[10px] text-gray-400 uppercase font-bold mb-1 tracking-wider">
                                                                Tactical Motifs
                                                            </div>
                                                            <div className="flex flex-wrap gap-1">
                                                                {currentPosition.motifs.map(motif => (
                                                                    <span 
                                                                        key={motif}
                                                                        className="bg-purple-50 text-purple-600 text-[10px] px-1.5 py-0.5 rounded font-medium border border-purple-100"
                                                                    >
                                                                        {motif.replace('-', ' ')}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            ) : (
                                                <button
                                                    onClick={() => setShowAnswer(true)}
                                                    className="w-full py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg font-medium text-sm hover:from-purple-700 hover:to-indigo-700 transition-all shadow-sm"
                                                >
                                                    👁️ Show Answer
                                                </button>
                                            )}
                                        </div>
                                    </>
                                ) : (
                                    <div className="text-gray-500 text-sm py-8">
                                        No positions generated
                                    </div>
                                )}
                            </div>

                            {/* Navigation - only show when not on original */}
                            {!showOriginal && positions.length > 1 && (
                                <div className="px-4 py-3 border-t flex items-center justify-between">
                                    <button
                                        onClick={() => goTo(Math.max(0, currentIndex - 1))}
                                        disabled={currentIndex === 0}
                                        className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                    >
                                        ← Prev
                                    </button>
                                    <span className="text-xs text-gray-400">
                                        {currentPosition?.method}
                                    </span>
                                    <button
                                        onClick={() => goTo(Math.min(positions.length - 1, currentIndex + 1))}
                                        disabled={currentIndex === positions.length - 1}
                                        className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                    >
                                        Next →
                                    </button>
                                </div>
                            )}

                            {/* Summary footer */}
                            {positions.length > 0 && (
                                <div className="px-4 py-2 bg-gray-50 border-t text-xs text-gray-400 text-center">
                                    {positions.length} practice positions generated •
                                    {positions.filter(p => p.difficulty === 'easy').length} easy, {' '}
                                    {positions.filter(p => p.difficulty === 'medium').length} medium, {' '}
                                    {positions.filter(p => p.difficulty === 'hard').length} hard
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
