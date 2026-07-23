import { NextRequest, NextResponse } from "next/server";
import { apiUrl } from "@/lib/api-base";

const COOKIE_NAME = "da_session";

export async function POST(request: NextRequest) {
  try {
    const token = request.cookies.get(COOKIE_NAME)?.value;
    const response = await fetch(apiUrl("/api/v1/current-affairs/practice/restart"), {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
    });
    return NextResponse.json(await response.json(), {
      status: response.status,
      headers: { "Cache-Control": "no-store, private" },
    });
  } catch (error: unknown) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Failed to restart progress" },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}
