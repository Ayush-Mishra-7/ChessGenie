import { NextResponse } from 'next/server'
import prisma from '@/lib/prisma'
import { verifyToken } from '@/lib/jwt'

export async function GET(req: Request) {
    try {
        const cookie = req.headers.get('cookie') || ''
        const tokenMatch = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('chessgenie_session='))
        const token = tokenMatch ? tokenMatch.split('=')[1] : null

        const decoded: any = token ? verifyToken(token) : null
        if (!decoded?.id) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const games = await prisma.gameAnalysis.findMany({
            where: { userId: decoded.id },
            orderBy: { createdAt: 'desc' },
            take: 50
        })

        return NextResponse.json({
            games: games.map(game => ({
                id: game.id,
                gameId: game.gameId,
                pgn: game.pgn,
                result: game.result,
                createdAt: game.createdAt.toISOString()
            }))
        })
    } catch (err) {
        console.error('Games list error:', err)
        return NextResponse.json({ error: 'Server error' }, { status: 500 })
    }
}
