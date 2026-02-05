import { NextResponse } from 'next/server'
import prisma from '@/lib/prisma'
import { verifyToken } from '@/lib/jwt'

async function validatePlatformKey(platform: string, username: string, apiKey: string | null) {
  try {
    if (platform === 'LICHESS') {
      if (apiKey) {
        const res = await fetch('https://lichess.org/api/account', { headers: { Authorization: `Bearer ${apiKey}` } })
        return res.ok
      }
      // No token: verify username exists
      const res = await fetch(`https://lichess.org/api/user/${encodeURIComponent(username)}`)
      return res.ok
    }

    if (platform === 'CHESS_COM') {
      const res = await fetch(`https://api.chess.com/pub/player/${encodeURIComponent(username)}`)
      return res.ok
    }

    return false
  } catch (e) {
    return false
  }
}

export async function POST(req: Request) {
  try {
    const cookie = req.headers.get('cookie') || ''
    const tokenMatch = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('chessgenie_session='))
    const token = tokenMatch ? tokenMatch.split('=')[1] : null

    const decoded: any = token ? verifyToken(token) : null
    if (!decoded?.id) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    // Optionally accept { id } to validate single key, otherwise validate all user's keys
    const body = await req.json().catch(() => ({}))
    const keyId = body.id

    const where = keyId ? { id: keyId } : { userId: decoded.id }

    const keys = keyId
      ? [await prisma.apiKey.findUnique({ where: { id: keyId } })]
      : await prisma.apiKey.findMany({ where: { userId: decoded.id } })

    const updates = []
    for (const k of keys) {
      if (!k) continue
      const ok = await validatePlatformKey(k.platform, k.username, k.apiKey || null)
      updates.push(
        prisma.apiKey.update({ where: { id: k.id }, data: { isValid: ok, lastChecked: new Date() } })
      )
    }

    await Promise.all(updates)

    return NextResponse.json({ ok: true })
  } catch (err) {
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
