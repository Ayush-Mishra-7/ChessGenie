import { NextResponse } from 'next/server'
import prisma from '@/lib/prisma'
import { verifyToken } from '@/lib/jwt'

export async function DELETE(
    req: Request,
    { params }: { params: { id: string } }
) {
    try {
        const cookie = req.headers.get('cookie') || ''
        const tokenMatch = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('chessgenie_session='))
        const token = tokenMatch ? tokenMatch.split('=')[1] : null

        const decoded: any = token ? verifyToken(token) : null
        if (!decoded?.id) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const gameId = params.id

        // Verify ownership
        const game = await prisma.gameAnalysis.findUnique({
            where: { id: gameId }
        })

        if (!game) {
            return NextResponse.json({ error: 'Game not found' }, { status: 404 })
        }

        if (game.userId !== decoded.id) {
            return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
        }

        // Delete the game analysis
        await prisma.gameAnalysis.delete({
            where: { id: gameId }
        })

        return NextResponse.json({ success: true })
    } catch (err) {
        console.error('Delete game error:', err)
        return NextResponse.json({ error: 'Server error' }, { status: 500 })
    }
}
