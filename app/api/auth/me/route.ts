import { NextResponse } from 'next/server'
import { verifyToken } from '@/lib/jwt'
import prisma from '@/lib/prisma'

export async function GET(req: Request) {
  try {
    const cookie = req.headers.get('cookie') || ''
    const match = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('chessgenie_session='))
    const token = match ? match.split('=')[1] : null

    if (!token) return NextResponse.json({ user: null })

    const decoded: any = verifyToken(token)
    if (!decoded?.id) return NextResponse.json({ user: null })

    const user = await prisma.user.findUnique({ where: { id: decoded.id }, select: { id: true, email: true, name: true } })

    return NextResponse.json({ user })
  } catch (err) {
    return NextResponse.json({ user: null })
  }
}
