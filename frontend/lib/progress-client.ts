export type LearningModule =
  | "reading_material" | "knowledge_mcqs" | "ai_generated_mcqs" | "chapter_practice" | "past_papers"
  | "current_affairs" | "danish_values" | "practice_questions" | "ai_chat" | "notes" | "mock_exam";

async function send(path: string, method: string, body?: unknown) {
  const response = await fetch(`/api/account/${path}`, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    keepalive: true,
  });
  if (!response.ok && response.status !== 401) throw new Error("Progress could not be saved");
  return response;
}

export function saveAttempt(input: {
  module: LearningModule; question_id: string; selected_choice?: string; correct_choice?: string;
  is_correct: boolean; topic?: string | null; track?: string; session_key?: string;
  client_attempt_id?: string; time_spent_seconds?: number; metadata?: Record<string, unknown>;
}) { return send("progress/attempts", "POST", input); }

export function saveLearningState(module: Exclude<LearningModule, "mock_exam">, input: {
  state_key?: string; route: string; entity_id?: string; title?: string;
  completion_percent?: number; state?: Record<string, unknown>; completed?: boolean;
}) { return send(`progress/states/${module}`, "PUT", input); }

export function saveRemoteNote(input: {
  module: LearningModule; entity_id: string; body: string; route?: string; anchor?: Record<string, unknown>;
}) { return send("progress/notes", "POST", input); }

export function saveRemoteBookmark(input: {
  module: LearningModule; entity_id: string; title?: string; route?: string; metadata?: Record<string, unknown>;
}) { return send("progress/bookmarks", "POST", input); }

export function saveCompletedMock(input: Record<string, unknown>) {
  return send("progress/mock-exams/completed", "POST", input);
}


export function saveStudyActivity(durationSeconds: number, route: string) {
  if (durationSeconds <= 0) return Promise.resolve(null);
  return send("progress/activity", "POST", {
    module: "practice_questions",
    activity_type: "study_presence",
    duration_seconds: Math.min(86400, Math.round(durationSeconds)),
    route,
    metadata: { source: "authenticated_browser_presence" }
  });
}

export function completeReadingChapter(input: {
  track: "pr" | "citizenship"; chapter_key: string; chapter_title: string;
  page_number: number; total_chapters: number; route?: string;
}) { return send("progress/chapters/complete", "POST", input); }

export function deleteRemoteNote(module: LearningModule, entityId: string) {
  return send("progress/notes/entity/" + encodeURIComponent(module) + "/" + encodeURIComponent(entityId), "DELETE");
}
