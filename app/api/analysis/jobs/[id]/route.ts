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

        const jobId = params.id

        // Verify ownership
        const job = await prisma.job.findUnique({
            where: { id: jobId }
        })

        if (!job) {
            return NextResponse.json({ error: 'Job not found' }, { status: 404 })
        }

        if (job.userId !== decoded.id) {
            return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
        }

        // Delete the job (Cascades to GameAnalysis due to schema relation)
        await prisma.job.delete({
            where: { id: jobId }
        })

        return NextResponse.json({ success: true })
    } catch (err) {
        console.error('Delete job error:', err)
        return NextResponse.json({ error: 'Server error' }, { status: 500 })
    }
}
