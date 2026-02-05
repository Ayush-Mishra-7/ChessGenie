"use client"

import { useMemo } from 'react'

type FenBoardProps = {
    fen: string
    width?: number
}

// Unicode chess pieces
const PIECES: Record<string, string> = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
}

export default function FenBoard({ fen, width = 320 }: FenBoardProps) {
    const board = useMemo(() => {
        // Parse FEN to 8x8 board
        const fenParts = fen.split(' ')
        const rows = fenParts[0].split('/')
        const squares: (string | null)[][] = []

        for (const row of rows) {
            const squareRow: (string | null)[] = []
            for (const char of row) {
                if (char >= '1' && char <= '8') {
                    // Empty squares
                    for (let i = 0; i < parseInt(char); i++) {
                        squareRow.push(null)
                    }
                } else {
                    squareRow.push(char)
                }
            }
            squares.push(squareRow)
        }
        return squares
    }, [fen])

    const squareSize = width / 8

    return (
        <div
            style={{
                width,
                height: width,
                display: 'grid',
                gridTemplateColumns: 'repeat(8, 1fr)',
                gridTemplateRows: 'repeat(8, 1fr)',
                border: '2px solid #333',
                borderRadius: '4px',
                overflow: 'hidden'
            }}
        >
            {board.map((row, rowIdx) =>
                row.map((piece, colIdx) => {
                    const isLight = (rowIdx + colIdx) % 2 === 0
                    const bgColor = isLight ? '#f0d9b5' : '#b58863'

                    return (
                        <div
                            key={`${rowIdx}-${colIdx}`}
                            style={{
                                backgroundColor: bgColor,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: squareSize * 0.75,
                                lineHeight: 1,
                                userSelect: 'none'
                            }}
                        >
                            {piece ? PIECES[piece] || '' : ''}
                        </div>
                    )
                })
            )}
        </div>
    )
}
