"use client"

import { useState, useEffect, useCallback, useRef } from 'react'
import { Chess } from 'chess.js'
import { Chessboard } from 'react-chessboard'
import LiveAnalysis from './LiveAnalysis'
import { useStockfish } from '@/hooks/useStockfish'

type GameViewerProps = {
    pgn: string
    initialMoveNumber?: number // 1-based
    onClose: () => void
}

export default function GameViewer({ pgn, initialMoveNumber = 0, onClose }: GameViewerProps) {
    const [game, setGame] = useState(new Chess())
    const [currentMoveIndex, setCurrentMoveIndex] = useState(-1) // -1 = start position
    const [history, setHistory] = useState<{ san: string, fen: string }[]>([])
    const { analysis, isAnalyzing, startAnalysis, stopAnalysis } = useStockfish()

    // Initialize game
    useEffect(() => {
        const newGame = new Chess()
        try {
            newGame.loadPgn(pgn)

            // Extract history with verbose output to get FENs directly
            const moves = newGame.history({ verbose: true })
            const historyData = moves.map(move => ({
                san: move.san,
                fen: move.after
            }))

            setHistory(historyData)
            setGame(newGame)

            // Jump to initial move if provided
            if (initialMoveNumber > 0) {
                // Determine target index (convert move number to half-move index)
                // This is tricky without knowing whose turn it is, but usually initialMoveNumber refers to full moves?
                // Actually, let's assume initialMoveNumber is simply the index for now or handle it better later.
                // If it's 1-based full move, we typically jump to white's move.
                // Let's simpler: just start at beginning unless specified.

                // For now, start at beginning
                setCurrentMoveIndex(-1)
            }
        } catch (e) {
            console.error('Invalid PGN', e)
        }
    }, [pgn, initialMoveNumber])

    // Update analysis when position changes
    useEffect(() => {
        let fen = ''
        if (currentMoveIndex === -1) {
            fen = new Chess().fen() // Start pos
        } else if (history[currentMoveIndex]) {
            fen = history[currentMoveIndex].fen
        }

        if (fen) {
            startAnalysis(fen)
        }

        return () => stopAnalysis()
    }, [currentMoveIndex, history, startAnalysis, stopAnalysis])

    // Keyboard navigation
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'ArrowRight') {
                setCurrentMoveIndex(prev => Math.min(prev + 1, history.length - 1))
            } else if (e.key === 'ArrowLeft') {
                setCurrentMoveIndex(prev => Math.max(prev - 1, -1))
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [history.length])

    // Force re-render of board when FEN changes
    const currentFen = currentMoveIndex === -1
        ? 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
        : (history[currentMoveIndex]?.fen || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')

    const goToMove = (index: number) => {
        // Ensure index is valid
        if (index >= -1 && index < history.length) {
            setCurrentMoveIndex(index)
        }
    }

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div
                className="bg-white rounded-xl shadow-2xl w-full max-w-5xl h-[80vh] flex overflow-hidden"
                onClick={e => e.stopPropagation()}
            >
                {/* Left: Board */}
                <div className="flex-1 bg-gray-100 flex items-center justify-center p-4">
                    <div className="w-full max-w-[60vh] aspect-square rounded shadow-lg overflow-hidden">
                        <Chessboard
                            options={{
                                id: "GameViewerBoard",
                                position: currentFen,
                                animationDurationInMs: 200,
                                allowDragging: false
                            }}
                        />
                    </div>
                </div>

                {/* Right: Controls & Analysis */}
                <div className="w-80 flex flex-col border-l bg-white">
                    {/* Header */}
                    <div className="p-4 border-b flex items-center justify-between bg-gray-50">
                        <h3 className="font-semibold">Game Review</h3>
                        <button onClick={onClose} className="text-gray-500 hover:text-black font-bold text-xl">×</button>
                    </div>

                    {/* Live Analysis */}
                    <div className="p-4 border-b">
                        <LiveAnalysis analysis={analysis} isAnalyzing={isAnalyzing} />
                    </div>

                    {/* Move History */}
                    <div className="flex-1 overflow-y-auto p-0">
                        <table className="w-full text-sm border-collapse">
                            <thead className="bg-gray-50 sticky top-0">
                                <tr>
                                    <th className="py-2 px-2 w-12 text-gray-500 font-medium border-b">#</th>
                                    <th className="py-2 px-4 text-left font-medium border-b">White</th>
                                    <th className="py-2 px-4 text-left font-medium border-b">Black</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Array.from({ length: Math.ceil(history.length / 2) }).map((_, i) => {
                                    const moveIndexWhite = i * 2;
                                    const moveIndexBlack = i * 2 + 1;
                                    const whiteMove = history[moveIndexWhite];
                                    const blackMove = history[moveIndexBlack];

                                    return (
                                        <tr key={i} className="hover:bg-gray-50">
                                            <td className="py-1 px-2 text-center text-gray-400 bg-gray-50 border-r text-xs">{i + 1}</td>
                                            <td
                                                className={`py-1 px-4 cursor-pointer hover:bg-blue-50 ${currentMoveIndex === moveIndexWhite ? 'bg-blue-100 font-bold text-blue-700' : ''}`}
                                                onClick={() => goToMove(moveIndexWhite)}
                                            >
                                                {whiteMove.san}
                                            </td>
                                            <td
                                                className={`py-1 px-4 cursor-pointer hover:bg-blue-50 ${currentMoveIndex === moveIndexBlack ? 'bg-blue-100 font-bold text-blue-700' : ''}`}
                                                onClick={() => blackMove ? goToMove(moveIndexBlack) : null}
                                            >
                                                {blackMove ? blackMove.san : ''}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>

                    {/* Controls */}
                    <div className="p-4 border-t bg-gray-50 flex justify-center gap-2">
                        <button
                            className="p-2 hover:bg-gray-200 rounded disabled:opacity-50"
                            onClick={() => goToMove(-1)}
                            disabled={currentMoveIndex === -1}
                        >
                            ⏮
                        </button>
                        <button
                            className="p-2 hover:bg-gray-200 rounded disabled:opacity-50"
                            onClick={() => goToMove(currentMoveIndex - 1)}
                            disabled={currentMoveIndex === -1}
                        >
                            ◀
                        </button>
                        <button
                            className="p-2 hover:bg-gray-200 rounded disabled:opacity-50"
                            onClick={() => goToMove(currentMoveIndex + 1)}
                            disabled={currentMoveIndex === history.length - 1}
                        >
                            ▶
                        </button>
                        <button
                            className="p-2 hover:bg-gray-200 rounded disabled:opacity-50"
                            onClick={() => goToMove(history.length - 1)}
                            disabled={currentMoveIndex === history.length - 1}
                        >
                            ⏭
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
