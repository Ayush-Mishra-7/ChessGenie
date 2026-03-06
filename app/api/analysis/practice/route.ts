import { NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000'

export async function POST(request: Request) {
    try {
        const body = await request.json()

        const res = await fetch(`${BACKEND_URL}/practice/generate-similar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        })

        if (!res.ok) {
            const contentType = res.headers.get('content-type') || ''
            let error = `Request failed with status ${res.status}`

            if (contentType.includes('application/json')) {
                const payload = await res.json()
                error = payload.detail || payload.error || error
            } else {
                const text = await res.text()
                if (text) {
                    error = text
                }
            }

            return NextResponse.json(
                { error },
                { status: res.status }
            )
        }

        const data = await res.json()
        return NextResponse.json(data)
    } catch (error: any) {
        console.error('Practice position generation failed:', error)
        return NextResponse.json(
            { error: error.message || 'Failed to generate positions' },
            { status: 500 }
        )
    }
}
