import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { authEnabled } from '@/auth.config';
import { SERVER_API_BASE_URL } from '@/lib/config';

export async function POST(request: Request) {
    if (!authEnabled) {
        return NextResponse.json({ error: 'Authentication is not configured' }, { status: 503 });
    }
    const session = await auth();
    if (!session) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const adminToken = process.env.ADMIN_TOKEN;
    if (!adminToken) {
        return NextResponse.json({ error: 'ADMIN_TOKEN is not configured on the server' }, { status: 503 });
    }

    const body = await request.json().catch(() => ({}));
    const extra = body && typeof body === 'object' && !Array.isArray(body) ? body : {};
    const response = await fetch(`${SERVER_API_BASE_URL}/push-user`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
        },
        // Identity fields come from the verified session and are applied last,
        // so the request body cannot overwrite them.
        body: JSON.stringify({
            ...extra,
            email: session.user?.email,
            name: session.user?.name,
            image: session.user?.image,
        }),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
}
