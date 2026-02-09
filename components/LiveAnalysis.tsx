import { useEffect, useState } from 'react'
import { AnalysisResult } from '@/hooks/useStockfish'

type LiveAnalysisProps = {
    analysis: AnalysisResult | null
    isAnalyzing: boolean
    className?: string
    orientation?: 'white' | 'black'
}

export default function LiveAnalysis({ analysis, isAnalyzing, className = '', orientation = 'white' }: LiveAnalysisProps) {
    if (!analysis && !isAnalyzing) return null

    // Get score from user's perspective
    // analysis.score is White-relative (positive = White winning)
    // If user is Black, we flip it so positive = Black winning
    const getUserScore = (score: number) => {
        return orientation === 'white' ? score : -score
    }

    const getUserMate = (mate?: number) => {
        if (mate === undefined) return undefined
        // mate is also White-relative (positive = White mates)
        // If user is Black, we flip it
        return orientation === 'white' ? mate : -mate
    }

    const getScoreText = (score: number, mate?: number) => {
        const userMate = getUserMate(mate)
        if (userMate !== undefined) {
            return `M${Math.abs(userMate)}`
        }

        const userScore = getUserScore(score)
        return (userScore / 100).toFixed(2)
    }

    const getBarHeight = (score: number, mate?: number) => {
        // Normalize score to 0-100% for the bar
        // Range: -500 to +500 cp (capped)
        // We want the bar to fill up if the user is winning

        let val = getUserScore(score)
        const userMate = getUserMate(mate)

        if (userMate !== undefined) {
            val = userMate > 0 ? 500 : -500
        }

        const capped = Math.max(-500, Math.min(500, val))
        const percent = 50 + (capped / 10) // 0 scores = 50%
        return Math.max(5, Math.min(95, percent)) // Keep bar visible
    }

    return (
        <div className={`bg-white rounded-lg border p-4 shadow-sm ${className}`}>
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${isAnalyzing ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`} />
                    <span className="font-semibold text-gray-700">Live Analysis</span>
                    {analysis && (
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                            Depth {analysis.depth}
                        </span>
                    )}
                </div>
                <div className="font-mono font-bold text-lg">
                    {analysis ? getScoreText(analysis.score, analysis.mate) : '...'}
                </div>
            </div>

            {/* Eval Bar & Score */}
            <div className="flex items-center gap-3 mb-4">
                <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden flex">
                    <div
                        className={`h-full transition-all duration-500 ease-out ${
                            // Change color based on who is winning (user perspective)
                            (analysis && getUserScore(analysis.score) >= 0) ? 'bg-green-600' : 'bg-gray-800'
                            }`}
                        style={{ width: `${analysis ? getBarHeight(analysis.score, analysis.mate) : 50}%` }}
                    />
                </div>
                <div className={`font-mono font-bold text-lg min-w-[3rem] text-right ${(analysis && getUserScore(analysis.score) > 0) ? 'text-green-600' : ''
                    }`}>
                    {analysis ? getScoreText(analysis.score, analysis.mate) : '...'}
                </div>
            </div>

            {/* Best Line */}
            {analysis?.bestLine && (
                <div className="text-sm">
                    <div className="text-gray-500 mb-1 text-xs uppercase tracking-wider font-semibold">Best Line</div>
                    <div className="font-mono text-gray-800 bg-gray-50 p-2 rounded break-words">
                        {analysis.bestLine.slice(0, 10).join(' ')}
                        {analysis.bestLine.length > 10 && ' ...'}
                    </div>
                </div>
            )}
        </div>
    )
}
