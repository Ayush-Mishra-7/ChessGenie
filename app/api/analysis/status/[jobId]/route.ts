import { NextResponse } from 'next/server'
import prisma from '@/lib/prisma'
import { verifyToken } from '@/lib/jwt'

export async function GET(
  req: Request,
  { params }: { params: { jobId: string } }
) {
  try {
    const cookie = req.headers.get('cookie') || ''
    const tokenMatch = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('chessgenie_session='))
    const token = tokenMatch ? tokenMatch.split('=')[1] : null

    const decoded: any = token ? verifyToken(token) : null
    if (!decoded?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { jobId } = params

    const job = await prisma.job.findUnique({
      where: { id: jobId }
    })

    if (!job) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 })
    }

    // Ensure user owns this job
    if (job.userId !== decoded.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
    }

    // Get game count if completed
    let gameCount = 0
    if (job.status === 'COMPLETED') {
      gameCount = await prisma.gameAnalysis.count({
        where: { jobId: jobId }
      })
    }

    return NextResponse.json({
      jobId: job.id,
      status: job.status,
      result: job.result,
      gameCount,
      createdAt: job.createdAt.toISOString(),
      updatedAt: job.updatedAt.toISOString()
    })
  } catch (err) {
    console.error('Job status error:', err)
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
