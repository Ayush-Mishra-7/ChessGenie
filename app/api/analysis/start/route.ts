import { NextResponse } from 'next/server'
import prisma from '@/lib/prisma'
import { verifyToken } from '@/lib/jwt'

export async function POST(req: Request) {
  try {
    const cookie = req.headers.get('cookie') || ''
    const tokenMatch = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('chessgenie_session='))
    const token = tokenMatch ? tokenMatch.split('=')[1] : null

    const decoded: any = token ? verifyToken(token) : null
    if (!decoded?.id) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const body = await req.json()
    const { platform, username, game_limit = 50, analysis_depth = 20 } = body
    if (!platform || !username) return NextResponse.json({ error: 'Missing fields' }, { status: 400 })

    const job = await prisma.job.create({
      data: {
        userId: decoded.id,
        type: 'ANALYZE_GAMES',
        status: 'QUEUED',
        payload: {
          platform,
          username,
          game_limit,
          analysis_depth
        }
      }
    })

    return NextResponse.json({ ok: true, jobId: job.id })
  } catch (err) {
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
