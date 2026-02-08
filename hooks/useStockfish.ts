import { useState, useEffect, useRef, useCallback } from 'react'

export type AnalysisResult = {
    depth: number
    score: number // centipawns
    mate?: number // turns to mate (positive = white wins, negative = black wins)
    bestMove: string // UCI
    bestLine: string[] // UCI moves
    isAnalyzing: boolean
}

type StockfishHook = {
    analysis: AnalysisResult | null
    isAnalyzing: boolean
    startAnalysis: (fen: string, depth?: number) => void
    stopAnalysis: () => void
}

export function useStockfish(): StockfishHook {
    const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const workerRef = useRef<Worker | null>(null)

    useEffect(() => {
        // Initialize worker
        try {
            const worker = new Worker('/stockfish.js')
            workerRef.current = worker

            worker.onmessage = (e) => {
                const line = e.data

                // Parse UCI output
                if (line.startsWith('info depth')) {
                    parseInfoLine(line)
                } else if (line.startsWith('bestmove')) {
                    setIsAnalyzing(false)
                }
            }

            worker.postMessage('uci')

            return () => {
                worker.terminate()
            }
        } catch (error) {
            console.error('Failed to initialize Stockfish worker:', error)
        }
    }, [])

    const parseInfoLine = (line: string) => {
        try {
            // Example: info depth 10 seldepth 15 multipv 1 score cp 24 nodes 1234 nps 4321 hashfull 0 tbhits 0 time 200 pv e2e4 e7e5
            const depthMatch = line.match(/depth (\d+)/)
            const scoreCpMatch = line.match(/score cp (-?\d+)/)
            const scoreMateMatch = line.match(/score mate (-?\d+)/)
            const pvMatch = line.match(/ pv (.+)/)

            if (depthMatch && (scoreCpMatch || scoreMateMatch)) {
                const depth = parseInt(depthMatch[1])
                const bestLine = pvMatch ? pvMatch[1].split(' ') : []
                const bestMove = bestLine[0] || ''

                let score = 0
                let mate = undefined

                if (scoreMateMatch) {
                    mate = parseInt(scoreMateMatch[1])
                    score = mate > 0 ? 10000 : -10000 // High score for mate
                } else if (scoreCpMatch) {
                    score = parseInt(scoreCpMatch[1])
                }

                setAnalysis(prev => ({
                    ...prev,
                    depth,
                    score,
                    mate,
                    bestMove,
                    bestLine,
                    isAnalyzing: true
                }))
            }
        } catch (e) {
            console.error('Error parsing engine output:', e)
        }
    }

    const startAnalysis = useCallback((fen: string, depth: number = 20) => {
        if (!workerRef.current) return

        console.log('Starting analysis for FEN:', fen)

        setIsAnalyzing(true)
        setAnalysis(null) // Clear previous analysis

        // Stop any previous analysis
        workerRef.current.postMessage('stop')

        // Start new analysis
        workerRef.current.postMessage(`position fen ${fen}`)
        workerRef.current.postMessage(`go depth ${depth}`)
    }, [])

    const stopAnalysis = useCallback(() => {
        if (workerRef.current) {
            workerRef.current.postMessage('stop')
            setIsAnalyzing(false)
        }
    }, [])

    return {
        analysis,
        isAnalyzing,
        startAnalysis,
        stopAnalysis
    }
}
