import { NextRequest, NextResponse } from "next/server";
import { apiUrl } from "@/lib/api-base";

const COOKIE_NAME = "da_session";

async function proxy(request: NextRequest, path: string[]) {
  const target = apiUrl(`/api/v1/chapter-practice/${path.join("/")}${request.nextUrl.search}`);
  const token = request.cookies.get(COOKIE_NAME)?.value;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.text();

  try {
    const upstream = await fetch(target, { method: request.method, headers, body, cache: "no-store" });
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
    return NextResponse.json(payload, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { detail: "Chapter practice is temporarily unavailable." },
      { status: 503 },
    );
  }
}

type Context = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}

export async function POST(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}
