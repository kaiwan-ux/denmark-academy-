import { NextRequest, NextResponse } from "next/server";
import { apiUrl } from "@/lib/api-base";
import { inferObjective, MockSelectionGuard } from "@/lib/mock-quality";

type TrackKey = "pr" | "citizenship";
type SectionKey = "knowledge" | "current_affairs" | "danish_values";
type ChoiceKey = "A" | "B" | "C" | "D";

type RawQuestion = Record<string, any>;

type MockQuestion = {
  id: string;
  section: SectionKey;
  source: "official" | "ai" | "current_affairs";
  stem: string;
  choices: { key: ChoiceKey; text: string }[];
  correct_choice: ChoiceKey;
  explanation?: string;
  paper_code?: string;
  learning_objective?: string;
  context_key?: string;
};

const allowedTracks = new Set<TrackKey>(["pr", "citizenship"]);

const blueprint = {
  citizenship: {
    title: "Danish Citizenship Test",
    officialName: "Indfoedsretsproeven",
    totalQuestions: 45,
    timeMinutes: 45,
    passingScore: 36,
    sections: { knowledge: 35, current_affairs: 5, danish_values: 5 },
    valuesPassingScore: 4,
    aiTarget: 6
  },
  pr: {
    title: "Permanent Residence Test",
    officialName: "Medborgerskabsproeven",
    totalQuestions: 25,
    timeMinutes: 30,
    passingScore: 20,
    sections: { knowledge: 25, current_affairs: 0, danish_values: 0 },
    valuesPassingScore: null,
    aiTarget: 5
  }
} as const;

const valueKeywords = [
  "demokrati",
  "grundlov",
  "frihed",
  "ytringsfrihed",
  "religionsfrihed",
  "ligestilling",
  "rettighed",
  "pligt",
  "retsstat",
  "folkestyre",
  "dansk vaerdi",
  "vÃƒÆ’Ã‚Â¦rd",
  "medborgerskab"
];

export async function POST(request: NextRequest) {
  try {
    const body = await request.json().catch(() => ({}));
    const track = (body.track ?? "citizenship") as TrackKey;

    if (!allowedTracks.has(track)) {
      return NextResponse.json({ error: "Unsupported exam track" }, { status: 400 });
    }

    const plan = blueprint[track];
    const [officialRows, crossBankReferences, history] = await Promise.all([
      fetchOfficialQuestions(track),
      fetchCrossBankReferences(track),
      fetchCompletedMockHistory(request, track),
    ]);
    const official = officialRows.filter((item) => !history.questionIds.has(questionId(item)));
    const ai = await ensureApprovedAiQuestions(track, history.questionIds);

    const used = new MockSelectionGuard();
    [...crossBankReferences, ...history.references].forEach((item) => used.addReference(
      String(item.stem ?? ""), String(item.learning_objective ?? ""),
    ));
    const questions: MockQuestion[] = [];

    if (track === "citizenship") {
      const valuesOfficial = official.filter(isDanishValuesQuestion);
      const nonValuesOfficial = official.filter((item) => !isDanishValuesQuestion(item));
      const hardAi = ai.filter((item) => String(item.difficulty ?? "hard") === "hard" && item.metadata?.rag_grounded === true);
      const aiKnowledgeQuestions = hardAi.filter((item) => item.section === "knowledge").map((item, index) => normalizeAiQuestion(item, `ai-knowledge-${index}`, "knowledge"));
      const aiValueQuestions = hardAi.filter((item) => item.section === "danish_values").map((item, index) => normalizeAiQuestion(item, `ai-values-${index}`, "danish_values"));
      const aiCurrentQuestions = hardAi.filter((item) => item.section === "current_affairs").map((item, index) => normalizeAiQuestion(item, `ai-current-${index}`, "current_affairs"));

      questions.push(...takeUnique(nonValuesOfficial, 30, used, "knowledge", "official"));
      questions.push(...takeAi(aiKnowledgeQuestions, 5, used, "knowledge"));
      fillFromOfficial(questions, official, used, "knowledge", plan.sections.knowledge);

      questions.push(...takeAi(aiCurrentQuestions, 5, used, "current_affairs"));
      fillFromOfficial(questions, nonValuesOfficial, used, "current_affairs", plan.sections.current_affairs);

      questions.push(...takeUnique(valuesOfficial, 4, used, "danish_values", "official"));
      questions.push(...takeAi(aiValueQuestions.length ? aiValueQuestions : aiKnowledgeQuestions, 1, used, "danish_values"));
      fillFromOfficial(questions, valuesOfficial.length ? valuesOfficial : official, used, "danish_values", plan.sections.danish_values);
    } else {
      const aiKnowledgeQuestions = ai.filter((item) => item.section === "knowledge" && String(item.difficulty ?? "hard") === "hard" && item.metadata?.rag_grounded === true).map((item, index) => normalizeAiQuestion(item, `ai-knowledge-${index}`, "knowledge"));
      questions.push(...takeUnique(official, 20, used, "knowledge", "official"));
      questions.push(...takeAi(aiKnowledgeQuestions, 5, used, "knowledge"));
      fillFromOfficial(questions, official, used, "knowledge", plan.sections.knowledge);
    }

    const finalQuestions = orderByBlueprint(track, questions).slice(0, plan.totalQuestions);
    if (finalQuestions.length !== plan.totalQuestions) {
      throw new Error(`Could not assemble ${plan.totalQuestions} validated, non-duplicate questions`);
    }

    return NextResponse.json({
      track,
      blueprint: plan,
      questions: finalQuestions,
      composition: summarize(finalQuestions),
      generated_at: new Date().toISOString()
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not assemble mock exam" },
      { status: 500 }
    );
  }
}

async function fetchOfficialQuestions(track: TrackKey) {
  const response = await fetch(apiUrl(`/api/v1/admin/official-questions?track=${track}&random_order=true&limit=180`), { cache: "no-store" });
  if (!response.ok) throw new Error("Official questions are not available. Start the backend and PostgreSQL first.");
  const rows = await response.json();
  return shuffle((rows ?? []) as RawQuestion[]);
}

async function fetchApprovedAiQuestions(track: TrackKey) {
  try {
    const response = await fetch(apiUrl(`/api/v1/admin/mock-ai-questions?track=${track}&status=approved&limit=200`), { cache: "no-store" });
    if (!response.ok) return [];
    const rows = await response.json();
    return shuffle((rows ?? []) as RawQuestion[]);
  } catch {
    return [];
  }
}

async function ensureApprovedAiQuestions(track: TrackKey, excludedIds: Set<string>) {
  let rows = await fetchApprovedAiQuestions(track);
  const requirements = track === "citizenship"
    ? { knowledge: 5, current_affairs: 5, danish_values: 1 }
    : { knowledge: 5, current_affairs: 0, danish_values: 0 };
  const usable = () => rows.filter((item) => !excludedIds.has(questionId(item)));
  const deficits = Object.entries(requirements).filter(([section, required]) =>
    usable().filter((item) => item.section === section && String(item.difficulty ?? "hard") === "hard" && item.metadata?.rag_grounded === true).length < required,
  );
  if (deficits.length) {
    await Promise.all(deficits.map(async ([section, required]) => {
      const existing = usable().filter((item) => item.section === section && String(item.difficulty ?? "hard") === "hard" && item.metadata?.rag_grounded === true).length;
      const response = await fetch(apiUrl("/api/v1/admin/mock-ai-questions/generate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track, section, count: Math.max(1, required - existing), difficulty: "hard", auto_approve: true }),
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Could not generate grounded ${section.replace("_", " ")} questions`);
    }));
    rows = await fetchApprovedAiQuestions(track);
  }
  return usable();
}

function questionId(item: RawQuestion): string {
  return String(item.id ?? item.content_sha256 ?? "");
}

async function fetchCompletedMockHistory(request: NextRequest, track: TrackKey) {
  const questionIds = new Set<string>();
  const references: RawQuestion[] = [];
  const token = request.cookies.get("da_session")?.value;
  if (!token) return { questionIds, references };
  const response = await fetch(apiUrl("/api/v1/progress/mock-exams"), {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Could not load previous mock history safely");
  const attempts = (await response.json()) as RawQuestion[];
  for (const attempt of attempts) {
    if (attempt.track !== track || !Array.isArray(attempt.answers)) continue;
    for (const answer of attempt.answers as RawQuestion[]) {
      const id = String(answer.question_id ?? "");
      if (id) questionIds.add(id);
      const stem = cleanQuestionText(answer.stem);
      if (stem) references.push({ stem, learning_objective: answer.learning_objective ?? "" });
    }
  }
  return { questionIds, references };
}
async function fetchCrossBankReferences(track: TrackKey) {
  const response = await fetch(apiUrl(`/api/v1/admin/mock-ai-questions/references?track=${track}&limit=1500`), { cache: "no-store" });
  if (!response.ok) return [];
  return (await response.json()) as RawQuestion[];
}

function normalizeOfficialQuestion(item: RawQuestion, section: SectionKey, source: "official" | "current_affairs"): MockQuestion {
  const id = String(item.id ?? item.content_sha256 ?? `${source}-${item.stem}`);
  return {
    id,
    section,
    source,
    stem: cleanQuestionText(item.stem ?? item.question_stem),
    choices: normalizeChoices(item),
    correct_choice: normalizeChoice(item.correct_choice),
    explanation: item.explanation ? cleanQuestionText(item.explanation) : undefined,
    paper_code: item.paper_code ? String(item.paper_code) : undefined,
    learning_objective: String(item.learning_objective ?? item.metadata?.learning_objective ?? inferObjective(String(item.stem ?? item.question_stem ?? ""))),
    context_key: String(item.context_key ?? `${item.paper_code ?? "official"}:${item.source_page_start ?? item.source_page ?? ""}`)
  };
}

function normalizeAiQuestion(item: RawQuestion, id: string, section: SectionKey): MockQuestion {
  return {
    id: String(item.id ?? `${id}-${item.stem ?? crypto.randomUUID()}`),
    section,
    source: "ai",
    stem: cleanQuestionText(item.stem ?? item.question_stem),
    choices: normalizeChoices(item),
    correct_choice: normalizeChoice(item.correct_choice),
    explanation: item.explanation ? cleanQuestionText(item.explanation) : undefined,
    learning_objective: String(item.learning_objective ?? item.metadata?.learning_objective ?? inferObjective(String(item.stem ?? item.question_stem ?? ""))),
    context_key: String(item.context_key ?? `${section}:${item.metadata?.grounding_source ?? ""}`)
  };
}

function normalizeChoices(item: RawQuestion) {
  const raw = [
    ["A", item.choice_a ?? item.choices?.A],
    ["B", item.choice_b ?? item.choices?.B],
    ["C", item.choice_c ?? item.choices?.C],
    ["D", item.choice_d ?? item.choices?.D]
  ] as const;
  return raw
    .filter((choice): choice is readonly [ChoiceKey, string] => typeof choice[1] === "string" && choice[1].trim().length > 0)
    .map(([key, text]) => ({ key, text: cleanQuestionText(text, true) }));
}

function cleanQuestionText(value: unknown, choice = false): string {
  let cleaned = String(value ?? "").replace(/[☐☑☒□▢◻◼]/gu, "");
  cleaned = cleaned.replace(/^\s*[.·•:;-]+\s*/u, "");
  if (choice) cleaned = cleaned.replace(/^\s*(?:[A-Da-d][.)]|\([A-Da-d]\))\s*/u, "");
  return cleaned.replace(/\s+/g, " ").trim();
}
function normalizeChoice(value: unknown): ChoiceKey {
  const choice = String(value ?? "A").toUpperCase();
  return choice === "B" || choice === "C" || choice === "D" ? choice : "A";
}

function takeUnique(source: RawQuestion[], count: number, used: MockSelectionGuard, section: SectionKey, kind: "official" | "current_affairs", enforceObjective = true) {
  const picked: MockQuestion[] = [];
  for (const item of source) {
    if (picked.length >= count) break;
    const question = normalizeOfficialQuestion(item, section, kind);
    if (!question.stem || question.choices.length < 2 || isAlreadyUsed(question, used, enforceObjective)) continue;
    markUsed(question, used);
    picked.push(question);
  }
  return picked;
}

function takeAi(source: MockQuestion[], count: number, used: MockSelectionGuard, section: SectionKey, enforceObjective = true) {
  const picked: MockQuestion[] = [];
  for (const item of source) {
    if (picked.length >= count) break;
    const question = { ...item, section };
    if (!question.stem || question.choices.length < 2 || isAlreadyUsed(question, used, enforceObjective)) continue;
    markUsed(question, used);
    picked.push(question);
  }
  return picked;
}

function isAlreadyUsed(question: MockQuestion, used: MockSelectionGuard, enforceObjective = true) {
  return !used.canAccept(question, enforceObjective);
}

function markUsed(question: MockQuestion, used: MockSelectionGuard) {
  used.add(question);
}

function fillFromOfficial(target: MockQuestion[], source: RawQuestion[], used: MockSelectionGuard, section: SectionKey, targetCount: number) {
  let needed = Math.max(0, targetCount - target.filter((question) => question.section === section).length);
  target.push(...takeUnique(source, needed, used, section, "official"));
  needed = Math.max(0, targetCount - target.filter((question) => question.section === section).length);
  if (needed) target.push(...takeUnique(source, needed, used, section, "official", false));
}

function isDanishValuesQuestion(item: RawQuestion) {
  const text = `${item.stem ?? ""} ${item.choice_a ?? ""} ${item.choice_b ?? ""} ${item.choice_c ?? ""}`.toLowerCase();
  return valueKeywords.some((keyword) => text.includes(keyword));
}

function orderByBlueprint(track: TrackKey, questions: MockQuestion[]) {
  if (track === "pr") return shuffle(questions);
  return [
    ...shuffle(questions.filter((question) => question.section === "knowledge")),
    ...shuffle(questions.filter((question) => question.section === "current_affairs")),
    ...shuffle(questions.filter((question) => question.section === "danish_values"))
  ];
}

function summarize(questions: MockQuestion[]) {
  return questions.reduce<Record<string, number>>((summary, question) => {
    const key = `${question.section}:${question.source}`;
    summary[key] = (summary[key] ?? 0) + 1;
    return summary;
  }, {});
}

function shuffle<T>(items: T[]) {
  return [...items]
    .map((item) => ({ item, sort: Math.random() }))
    .sort((a, b) => a.sort - b.sort)
    .map(({ item }) => item);
}
