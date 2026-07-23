import { NextRequest, NextResponse } from "next/server";
import { apiUrl } from "@/lib/api-base";

const COOKIE_NAME = "da_session";

export async function POST(request: NextRequest) {
  try {
    const token = request.cookies.get(COOKIE_NAME)?.value;
    const response = await fetch(apiUrl("/api/v1/current-affairs/practice"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: await request.text(),
      cache: "no-store",
    });
    const data = await response.json();
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": "no-store, private" },
    });
  } catch (error: unknown) {
    console.error("Current affairs practice error:", error);
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Failed to start practice session" },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}
