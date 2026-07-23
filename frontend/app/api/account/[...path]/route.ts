import { NextRequest, NextResponse } from "next/server";
import { apiUrl } from "@/lib/api-base";

const COOKIE_NAME = "da_session";

async function proxy(request: NextRequest, path: string[]) {
  const target = apiUrl(`/api/v1/${path.join("/")}${request.nextUrl.search}`);
  const token = request.cookies.get(COOKIE_NAME)?.value;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.text();

  let upstream: Response;
  try {
    upstream = await fetch(target, { method: request.method, headers, body, cache: "no-store" });
  } catch {
    return NextResponse.json({ detail: "The account service is temporarily unavailable." }, { status: 503 });
  }

  const text = await upstream.text();
  let payload: unknown = null;
  if (text) {
    try { payload = JSON.parse(text); } catch { payload = { detail: text }; }
  }

  if (upstream.status === 401 && token) {
    const response = NextResponse.json(payload ?? { detail: "Session expired" }, { status: 401 });
    response.cookies.delete(COOKIE_NAME);
    return response;
  }

  const isAuthSuccess =
    upstream.ok &&
    (path.join("/") === "auth/login" || path.join("/") === "auth/signup") &&
    payload &&
    typeof payload === "object" &&
    "session_token" in payload;

  if (isAuthSuccess) {
    const authPayload = payload as { session_token: string; expires_at: string; user: unknown };
    const response = NextResponse.json({ user: authPayload.user }, { status: upstream.status });
    response.cookies.set(COOKIE_NAME, authPayload.session_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      expires: new Date(authPayload.expires_at),
    });
    return response;
  }

  if (path.join("/") === "auth/logout") {
    const response = new NextResponse(null, { status: upstream.ok ? 204 : upstream.status });
    response.cookies.delete(COOKIE_NAME);
    return response;
  }

  return NextResponse.json(payload, { status: upstream.status });
}

type Context = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}
export async function POST(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}
export async function PUT(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}
export async function PATCH(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}
export async function DELETE(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}

