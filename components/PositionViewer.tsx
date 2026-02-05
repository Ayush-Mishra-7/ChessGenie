"use client"

import FenBoard from './FenBoard'

type PositionViewerProps = {
    fen: string
    playedMove: string
    bestMove: string
    onClose: () => void
}

export default function PositionViewer({ fen, playedMove, bestMove, onClose }: PositionViewerProps) {
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
                <div className="p-4 flex justify-center">
                    <FenBoard fen={fen} width={320} />
                </div>

                {/* Move Info */}
                <div className="p-4 border-t bg-gray-50 space-y-2">
                    <div className="flex items-center gap-2">
                        <span className="bg-red-100 text-red-700 text-xs font-medium px-2 py-1 rounded">
                            ❌ Played
                        </span>
                        <code className="text-sm font-mono bg-gray-100 px-2 py-1 rounded">
                            {playedMove}
                        </code>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="bg-green-100 text-green-700 text-xs font-medium px-2 py-1 rounded">
                            ✅ Best
                        </span>
                        <code className="text-sm font-mono bg-gray-100 px-2 py-1 rounded">
                            {bestMove}
                        </code>
                    </div>
                </div>
            </div>
        </div>
    )
}
