import { NextResponse } from 'next/server'
import prisma from '@/lib/prisma'
import { verifyToken } from '@/lib/jwt'
import { encrypt } from '@/lib/encryption'

type Platform = 'LICHESS' | 'CHESS_COM'

async function validateUsername(platform: Platform, username: string): Promise<boolean> {
  try {
    if (platform === 'LICHESS') {
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

export async function GET(req: Request) {
  try {
    const cookie = req.headers.get('cookie') || ''
    const tokenMatch = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('chessgenie_session='))
    const token = tokenMatch ? tokenMatch.split('=')[1] : null

    const decoded: any = token ? verifyToken(token) : null
    if (!decoded?.id) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const keys = await prisma.apiKey.findMany({ where: { userId: decoded.id }, orderBy: { createdAt: 'desc' } })
    const out = keys.map(k => ({ id: k.id, platform: k.platform, username: k.username, isValid: k.isValid, lastChecked: k.lastChecked, createdAt: k.createdAt }))

    return NextResponse.json({ keys: out })
  } catch (err) {
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}

export async function POST(req: Request) {
  try {
    const cookie = req.headers.get('cookie') || ''
    const tokenMatch = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('chessgenie_session='))
    const token = tokenMatch ? tokenMatch.split('=')[1] : null

    const decoded: any = token ? verifyToken(token) : null
    if (!decoded?.id) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const { platform, username, apiKey } = await req.json()
    if (!platform || !username || !apiKey) {
      return NextResponse.json({ error: 'Missing fields' }, { status: 400 })
    }

    const plat = platform as Platform
    const userExists = await validateUsername(plat, username)
    if (!userExists) {
      return NextResponse.json({ error: 'Username not found on platform' }, { status: 400 })
    }

    const encryptedKey = encrypt(apiKey)

    const saved = await prisma.apiKey.create({
      data: {
        userId: decoded.id,
        platform: plat as any,
        username,
        apiKey: encryptedKey,
        isValid: true
      }
    })

    return NextResponse.json({ ok: true, id: saved.id })
  } catch (err) {
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}

export async function DELETE(req: Request) {
  try {
    const cookie = req.headers.get('cookie') || ''
    const tokenMatch = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('chessgenie_session='))
    const token = tokenMatch ? tokenMatch.split('=')[1] : null

    const decoded: any = token ? verifyToken(token) : null
    if (!decoded?.id) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const { id } = await req.json()
    if (!id) return NextResponse.json({ error: 'Missing id' }, { status: 400 })

    // Ensure ownership
    const existing = await prisma.apiKey.findUnique({ where: { id } })
    if (!existing || existing.userId !== decoded.id) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 })
    }

    await prisma.apiKey.delete({ where: { id } })
    return NextResponse.json({ ok: true })
  } catch (err) {
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
