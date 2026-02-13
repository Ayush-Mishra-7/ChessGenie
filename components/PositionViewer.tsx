"use client"

import { useEffect, useMemo } from 'react'
import { Chessboard } from 'react-chessboard'
import LiveAnalysis from './LiveAnalysis'
import { useStockfish } from '@/hooks/useStockfish'

type PositionViewerProps = {
    fen: string
    playedMove: string
    bestMove: string
    playedUci?: string
    bestUci?: string
    onClose: () => void
    orientation?: 'white' | 'black'
    whitePlayer?: string
    blackPlayer?: string
}

/**
 * Convert a UCI move string (e.g. "e2e4") to arrow squares.
 * Returns { startSquare, endSquare } or null if invalid.
 */
function uciToSquares(uci?: string): { startSquare: string; endSquare: string } | null {
    if (!uci || uci.length < 4) return null
    const from = uci.substring(0, 2)
    const to = uci.substring(2, 4)
    // Validate squares are in range a-h, 1-8
    if (!/^[a-h][1-8]$/.test(from) || !/^[a-h][1-8]$/.test(to)) return null
    return { startSquare: from, endSquare: to }
}

export default function PositionViewer({
    fen,
    playedMove,
    bestMove,
    playedUci,
    bestUci,
    onClose,
    orientation = 'white',
    whitePlayer = 'White',
    blackPlayer = 'Black'
}: PositionViewerProps) {
    const { analysis, isAnalyzing, startAnalysis, stopAnalysis } = useStockfish()

    useEffect(() => {
        // Start analysis when modal opens
        startAnalysis(fen)
        return () => stopAnalysis()
    }, [fen, startAnalysis, stopAnalysis])

    const topPlayer = orientation === 'white' ? blackPlayer : whitePlayer
    const bottomPlayer = orientation === 'white' ? whitePlayer : blackPlayer

    // Build arrows: red for played move (mistake), green for best move
    const arrows = useMemo(() => {
        const result: { startSquare: string; endSquare: string; color: string }[] = []

        const bestSquares = uciToSquares(bestUci)
        if (bestSquares) {
            result.push({
                startSquare: bestSquares.startSquare,
                endSquare: bestSquares.endSquare,
                color: 'rgba(0, 180, 0, 0.7)'  // Green - best move
            })
        }

        const playedSquares = uciToSquares(playedUci)
        if (playedSquares) {
            result.push({
                startSquare: playedSquares.startSquare,
                endSquare: playedSquares.endSquare,
                color: 'rgba(220, 50, 50, 0.7)'  // Red - played (mistake)
            })
        }

        return result
    }, [playedUci, bestUci])

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div
                className="bg-white rounded-xl shadow-2xl max-w-md w-full overflow-hidden"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="bg-gray-800 text-white p-4 flex items-center justify-between">
                    <h3 className="font-semibold">Position Viewer</h3>
                    <button
                        onClick={onClose}
                        className="text-white/80 hover:text-white text-xl font-bold"
                    >
                        ×
                    </button>
                </div>

                {/* Board */}
                <div className="p-4 flex flex-col items-center justify-center bg-gray-100 gap-2">
                    {/* Top Player */}
                    <div className="w-[320px] flex items-center gap-2 text-gray-700 font-semibold text-sm">
                        <div className="w-6 h-6 bg-gray-300 rounded-full flex items-center justify-center text-gray-600">
                            👤
                        </div>
                        {topPlayer}
                    </div>

                    <div className="w-[320px] h-[320px] rounded shadow overflow-hidden">
                        <Chessboard
                            key={fen}
                            options={{
                                id: "position-viewer-board",
                                position: fen,
                                animationDurationInMs: 0,
                                allowDragging: false,
                                boardOrientation: orientation,
                                arrows: arrows,
                            }}
                        />
                    </div>

                    {/* Bottom Player */}
                    <div className="w-[320px] flex items-center gap-2 text-gray-700 font-semibold text-sm">
                        <div className="w-6 h-6 bg-gray-300 rounded-full flex items-center justify-center text-gray-600">
                            👤
                        </div>
                        {bottomPlayer}
                    </div>

                    {/* Arrow Legend */}
                    {(playedUci || bestUci) && (
                        <div className="w-[320px] flex items-center justify-center gap-4 text-xs text-gray-500 mt-1">
                            {playedUci && (
                                <span className="flex items-center gap-1">
                                    <span className="inline-block w-3 h-1.5 rounded" style={{ backgroundColor: 'rgba(220, 50, 50, 0.7)' }}></span>
                                    Played
                                </span>
                            )}
                            {bestUci && (
                                <span className="flex items-center gap-1">
                                    <span className="inline-block w-3 h-1.5 rounded" style={{ backgroundColor: 'rgba(0, 180, 0, 0.7)' }}></span>
                                    Best
                                </span>
                            )}
                        </div>
                    )}
                </div>

                {/* Live Analysis */}
                <div className="px-4 pb-2">
                    <LiveAnalysis analysis={analysis} isAnalyzing={isAnalyzing} orientation={orientation} />
                </div>

                {/* Move Comparison */}
                <div className="p-4 border-t bg-gray-50 grid grid-cols-2 gap-4">
                    <div className="bg-white p-2 rounded border border-red-100 shadow-sm">
                        <div className="text-xs text-gray-500 uppercase font-semibold mb-1 text-center">Played</div>
                        <div className="flex items-center justify-center gap-2">
                            <span className="text-red-600 font-bold font-mono text-lg">{playedMove}</span>
                            <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">Mistake</span>
                        </div>
                    </div>
                    <div className="bg-white p-2 rounded border border-green-100 shadow-sm">
                        <div className="text-xs text-gray-500 uppercase font-semibold mb-1 text-center">Best Move</div>
                        <div className="flex items-center justify-center gap-2">
                            <span className="text-green-600 font-bold font-mono text-lg">{bestMove}</span>
                            <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">Best</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
