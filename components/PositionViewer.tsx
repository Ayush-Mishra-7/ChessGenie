"use client"

import { useEffect } from 'react'
import { Chessboard } from 'react-chessboard'
import LiveAnalysis from './LiveAnalysis'
import { useStockfish } from '@/hooks/useStockfish'

type PositionViewerProps = {
    fen: string
    playedMove: string
    bestMove: string
    onClose: () => void
    orientation?: 'white' | 'black'
    whitePlayer?: string
    blackPlayer?: string
}

export default function PositionViewer({
    fen,
    playedMove,
    bestMove,
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
                                boardOrientation: orientation
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
