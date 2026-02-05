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

        // Fetch games with their job info
        const games = await prisma.gameAnalysis.findMany({
            where: { userId: decoded.id },
            orderBy: { createdAt: 'desc' },
            take: 100
        })

        // Fetch jobs for grouping
        const jobs = await prisma.job.findMany({
            where: { userId: decoded.id },
            orderBy: { createdAt: 'desc' },
            take: 20
        })

        // Create job summaries for grouping
        const jobSummaries = jobs.map(job => ({
            id: job.id,
            status: job.status,
            createdAt: job.createdAt.toISOString(),
            payload: job.payload as any,
            gameCount: games.filter(g => g.jobId === job.id).length
        }))

        return NextResponse.json({
            games: games.map(game => ({
                id: game.id,
                gameId: game.gameId,
                jobId: game.jobId,  // Include jobId for grouping
                pgn: game.pgn,
                result: game.result,
                createdAt: game.createdAt.toISOString()
            })),
            jobs: jobSummaries  // Include job summaries
        })
    } catch (err) {
        console.error('Games list error:', err)
        return NextResponse.json({ error: 'Server error' }, { status: 500 })
    }
}
