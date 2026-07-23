import { apiUrl } from "@/lib/api-base";

export type Track = "pr" | "citizenship";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: (userId: string, track: Track) => request(`/api/v1/users/${userId}/tracks/${track}/dashboard`),
  course: (track: Track) => request(`/api/v1/tracks/${track}/course`),
  learningUnit: (unitId: string, userId?: string) => request(`/api/v1/learning-units/${unitId}${userId ? `?user_id=${userId}` : ""}`),
  search: (body: unknown) => request(`/api/v1/search`, { method: "POST", body: JSON.stringify(body) }),
  createPractice: (body: unknown) => request(`/api/v1/practice/sessions`, { method: "POST", body: JSON.stringify(body) }),
  getPractice: (sessionId: string) => request(`/api/v1/practice/sessions/${sessionId}`),
  revision: (userId: string, track: Track) => request(`/api/v1/users/${userId}/tracks/${track}/revision`),
};
