import { NextResponse } from "next/server";
import { apiUrl } from "@/lib/api-base";

const allowedTracks = new Set(["pr", "citizenship"]);

function shuffle<T>(items: T[]) {
  return [...items]
    .map((item) => ({ item, sort: Math.random() }))
    .sort((a, b) => a.sort - b.sort)
    .map(({ item }) => item);
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const track = searchParams.get("track") ?? "citizenship";

  if (!allowedTracks.has(track)) {
    return NextResponse.json({ error: "Unsupported track" }, { status: 400 });
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(apiUrl(`/api/v1/admin/official-questions?track=${track}&random_order=false&limit=500`), {
      next: { revalidate: 3600 },
      signal: controller.signal
    });

    if (!response.ok) {
      return NextResponse.json({ error: "Could not load official questions" }, { status: response.status });
    }

    const questions = await response.json();
    return NextResponse.json({ track, questions }, { headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400" } });
  } catch (error) {
    const message = error instanceof Error && error.name === "AbortError"
      ? "Practice service timed out. Make sure PostgreSQL and the API are running."
      : "Practice service is not running.";
    return NextResponse.json({ error: message }, { status: 503 });
  } finally {
    clearTimeout(timeout);
  }
}