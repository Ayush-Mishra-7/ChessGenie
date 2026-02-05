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

        const jobs = await prisma.job.findMany({
            where: { userId: decoded.id },
            orderBy: { createdAt: 'desc' },
            take: 10
        })

        return NextResponse.json({
            jobs: jobs.map(job => ({
                id: job.id,
                status: job.status,
                payload: job.payload,
                result: job.result,
                createdAt: job.createdAt.toISOString(),
                updatedAt: job.updatedAt.toISOString()
            }))
        })
    } catch (err) {
        console.error('Jobs list error:', err)
        return NextResponse.json({ error: 'Server error' }, { status: 500 })
    }
}
