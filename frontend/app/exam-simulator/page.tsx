"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, CheckCircle2, Clock3, FileText, NotebookPen, RotateCcw, Send, XCircle } from "lucide-react";
import { saveCompletedMock, saveRemoteNote } from "@/lib/progress-client";
import { useLanguage } from "@/components/language-provider";

type TrackKey = "pr" | "citizenship";
type SectionKey = "knowledge" | "current_affairs" | "danish_values";
type ChoiceKey = "A" | "B" | "C" | "D";
type ExamState = "setup" | "loading" | "ready" | "finished" | "error";

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

type MockBlueprint = {
  title: string;
  officialName: string;
  totalQuestions: number;
  timeMinutes: number;
  passingScore: number;
  sections: Record<SectionKey, number>;
  valuesPassingScore: number | null;
};

type MockPayload = {
  track: TrackKey;
  blueprint: MockBlueprint;
  questions: MockQuestion[];
  composition: Record<string, number>;
};

const trackLabels: Record<TrackKey, string> = {
  citizenship: "Citizenship",
  pr: "Permanent Residence"
};

const sectionLabels: Record<SectionKey, string> = {
  knowledge: "Knowledge Base",
  current_affairs: "Current Affairs",
  danish_values: "Danish Values"
};

const sectionDescriptions: Record<SectionKey, string> = {
  knowledge: "Official learning material with selected past-paper anchors and hard AI enrichment.",
  current_affairs: "Recent Denmark-focused practice items from the current-affairs pipeline.",
  danish_values: "Values, rights, duties, democracy, freedom, and civic principles."
};

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const rest = Math.max(0, seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${rest}`;
}

function noteKey(track: TrackKey) {
  return `denmark-academy-mock-notes-${track}`;
}

export default function ExamSimulatorPage() {
  const { t } = useLanguage();
  const [track, setTrack] = useState<TrackKey>("citizenship");
  const [state, setState] = useState<ExamState>("setup");
  const [payload, setPayload] = useState<MockPayload | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, ChoiceKey>>({});
  const [notes, setNotes] = useState("");
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [error, setError] = useState("");
  const savedCompletion = useRef<string | null>(null);
  const completionSave = useRef<Promise<unknown> | null>(null);

  const questions = payload?.questions ?? [];
  const blueprint = payload?.blueprint;
  const current = questions[currentIndex];
  const answeredCount = Object.keys(answers).length;
  const examRunning = state === "ready";

  useEffect(() => {
    const stored = window.localStorage.getItem(noteKey(track));
    setNotes(stored ?? "");
  }, [track]);

  useEffect(() => {
    window.localStorage.setItem(noteKey(track), notes);
    if (!notes.trim()) return;
    const timer = window.setTimeout(() => {
      void saveRemoteNote({ module: "notes", entity_id: "mock-scratch-" + track, body: notes, route: "/exam-simulator", anchor: { track, kind: "mock_scratch" } });
    }, 700);
    return () => window.clearTimeout(timer);
  }, [notes, track]);

  useEffect(() => {
    if (!examRunning || remainingSeconds <= 0) return;
    const interval = window.setInterval(() => {
      setRemainingSeconds((value) => {
        if (value <= 1) {
          window.clearInterval(interval);
          setState("finished");
          return 0;
        }
        return value - 1;
      });
    }, 1000);
    return () => window.clearInterval(interval);
  }, [examRunning, remainingSeconds]);

  const result = useMemo(() => {
    if (!payload) return null;
    const correct = questions.filter((question) => answers[question.id] === question.correct_choice).length;
    const valuesQuestions = questions.filter((question) => question.section === "danish_values");
    const valuesCorrect = valuesQuestions.filter((question) => answers[question.id] === question.correct_choice).length;
    const totalPassed = correct >= payload.blueprint.passingScore;
    const valuesPassed = payload.track !== "citizenship" || valuesCorrect >= (payload.blueprint.valuesPassingScore ?? 0);
    return { correct, total: questions.length, valuesCorrect, valuesTotal: valuesQuestions.length, passed: totalPassed && valuesPassed, totalPassed, valuesPassed };
  }, [answers, payload, questions]);

  useEffect(() => {
    if (state !== "finished" || !payload || !result) return;
    const completionKey = payload.track + ":" + payload.blueprint.title + ":" + Object.keys(answers).sort().join(",");
    if (savedCompletion.current === completionKey) return;
    savedCompletion.current = completionKey;
    const save = saveCompletedMock({
      track: payload.track,
      score: result.correct,
      total_questions: result.total,
      correct_answers: result.correct,
      incorrect_answers: result.total - result.correct,
      duration_seconds: Math.max(0, payload.blueprint.timeMinutes * 60 - remainingSeconds),
      answers: questions.map((question) => ({ question_id: question.id, stem: question.stem, learning_objective: question.learning_objective ?? "", source: question.source, selected_choice: answers[question.id] ?? null, correct_choice: question.correct_choice, is_correct: answers[question.id] === question.correct_choice, section: question.section })),
      insights: { passed: result.passed, values_correct: result.valuesCorrect, values_total: result.valuesTotal }
    });
    completionSave.current = save;
    void save.catch(() => undefined);
  }, [state, payload, result, answers, questions, remainingSeconds]);
  async function startExam(nextTrack = track) {
    setState("loading");
    setError("");
    setAnswers({});
    savedCompletion.current = null;
    setCurrentIndex(0);

    try {
      const response = await fetch("/api/mock-exam", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track: nextTrack }),
        cache: "no-store"
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? "Could not assemble mock exam");
      setPayload(data as MockPayload);
      setRemainingSeconds((data.blueprint.timeMinutes ?? 30) * 60);
      setState("ready");
    } catch (caught) {
      setPayload(null);
      setError(caught instanceof Error ? caught.message : "Could not assemble mock exam");
      setState("error");
    }
  }

  function chooseTrack(nextTrack: TrackKey) {
    setTrack(nextTrack);
    setPayload(null);
    setAnswers({});
    savedCompletion.current = null;
    setCurrentIndex(0);
    setRemainingSeconds(0);
    setState("setup");
  }

  function answer(choice: ChoiceKey) {
    if (!current || state !== "ready") return;
    setAnswers((value) => ({ ...value, [current.id]: choice }));
  }

  function goTo(index: number) {
    setCurrentIndex(Math.max(0, Math.min(index, questions.length - 1)));
  }

  function finishExam() {
    setState("finished");
  }

  async function restart() {
    try {
      await completionSave.current;
    } catch {
      setError("Your completed paper could not be saved. Please try again before starting a new paper.");
      return;
    }
    await startExam(track);
  }

  const selected = current ? answers[current.id] : undefined;
  const progressPercent = blueprint ? Math.round((answeredCount / blueprint.totalQuestions) * 100) : 0;

  return (
    <div className={`practice-page mock-exam-page space-y-8 pb-6 ${state === "finished" ? "mock-exam-finished" : ""}`}>
      <section className="motion-panel mx-auto max-w-5xl text-center">
        <div className="text-xs font-semibold uppercase tracking-[0.3em] text-brass/75">Mock Exam</div>
        <h1 className="aesthetic-serif-strong mt-3 text-5xl leading-tight sm:text-6xl">A timed paper in a quiet exam room.</h1>
        <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-[#c8ad88]">Experience the real exam format with authentic questions, time limits, and scoring rules.</p>
      </section>

      <section className="motion-panel rounded-[18px] border border-[#6f4324]/60 bg-[radial-gradient(circle_at_50%_0%,rgba(214,168,79,0.18),transparent_28rem),linear-gradient(135deg,#2a150b,#120805)] p-3 shadow-[0_34px_150px_rgba(0,0,0,0.5)] sm:p-5">
        <div className="rounded-[14px] border border-black/40 bg-[#2a160c] p-2 shadow-[inset_0_0_0_1px_rgba(255,226,168,0.08)]">
          <div className="grid overflow-hidden rounded-[11px] bg-[#3a2112] shadow-[inset_0_0_38px_rgba(0,0,0,0.5)] xl:grid-cols-[300px_1fr_300px]">
            <aside className="relative min-h-[760px] bg-[#d9bf91] p-6 text-[#2b180c] shadow-[inset_-28px_0_44px_rgba(74,39,18,0.2)]">
              <div className="absolute right-0 top-0 h-full w-6 bg-gradient-to-r from-transparent to-[#70421f]/30" />
              <div className="relative z-10">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]"><BookOpen size={15} aria-hidden />Exam paper</div>
                <div className="mt-5 grid gap-3">
                  {(["citizenship", "pr"] as TrackKey[]).map((item) => (
                    <button key={item} type="button" onClick={() => chooseTrack(item)} disabled={state === "loading"} className={`rounded-[8px] border px-4 py-4 text-left transition ${item === track ? "border-[#5e331a] bg-[#5e331a] text-[#f7ead4] shadow-[0_14px_34px_rgba(80,39,16,0.28)]" : "border-[#946333]/50 bg-[#ead6b2]/70 text-[#4b2a14] hover:border-[#5e331a]"}`}>
                      <span className="block text-sm font-bold">{t(trackLabels[item])}</span>
                      <span className="mt-1 block text-xs opacity-80">{t(item === "citizenship" ? "45 questions · 45 minutes" : "25 questions · 30 minutes")}</span>
                    </button>
                  ))}
                </div>

                <div className="mt-8 rounded-[10px] border border-[#946333]/45 bg-[#efe0bf]/60 p-4">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[#70421f]"><Clock3 size={14} aria-hidden />Timer</div>
                  <div className={`mt-3 text-4xl font-bold tabular-nums ${remainingSeconds < 300 && state === "ready" ? "text-[#823433]" : "text-[#2f190b]"}`}>{formatTime(remainingSeconds)}</div>
                  <div className="mt-2 text-sm text-[#654223]">{blueprint ? `${blueprint.passingScore}/${blueprint.totalQuestions} required` : "Select a paper to begin"}</div>
                </div>

                <div className="mt-5 rounded-[10px] border border-[#946333]/45 bg-[#efe0bf]/60 p-4">
                  <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#70421f]">Progress</div>
                  <div className="mt-3 h-2 rounded-full bg-[#70421f]/18"><div className="h-2 rounded-full bg-[#70421f]" style={{ width: `${progressPercent}%` }} /></div>
                  <div className="mt-2 text-sm text-[#4b2a14]"><strong>{answeredCount}</strong> answered</div>
                </div>

                {state === "setup" || state === "error" ? (
                  <button type="button" onClick={() => startExam()} className="mt-5 inline-flex h-11 w-full items-center justify-center gap-2 rounded-[8px] bg-[#72401f] px-4 text-sm font-bold text-[#f7ead4]">
                    <FileText size={16} aria-hidden />Start mock exam
                  </button>
                ) : null}
              </div>
            </aside>

            <main className="relative min-h-[760px] bg-[#ead6b2] p-5 text-[#2b180c] shadow-[inset_28px_0_44px_rgba(74,39,18,0.18),inset_-22px_0_40px_rgba(74,39,18,0.12)] sm:p-8">
              <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-[#70421f]/18 to-transparent" />
              <div className="relative z-10 flex min-h-full flex-col">
                <div className="mb-7 flex flex-wrap items-end justify-between gap-3 border-b border-[#9b7149]/25 pb-4">
                  <div>
                    <div className="text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]">{blueprint?.officialName ?? t("Exam simulator")}</div>
                    <h2 className="mt-1 text-3xl font-bold tracking-tight text-[#3a210f]">{blueprint?.title ?? t("Choose your test")}</h2>
                  </div>
                  <div className="text-sm font-semibold text-[#7b5636]">{questions.length ? (currentIndex + 1) + " / " + questions.length : t("Not started")}</div>
                </div>

                {state === "setup" ? (
                  <EmptyState title={t("Prepare a full mock paper")} detail={t("Choose your exam track above. The paper will include official questions, current affairs when available, and challenging AI-generated items.")} />
                ) : state === "loading" ? (
                  <EmptyState title={t("Assembling exam paper...")} detail={t("Selecting questions across different sections and difficulty levels.")} />
                ) : state === "error" ? (
                  <EmptyState title="Mock could not start" detail={error} />
                ) : state === "finished" && result ? (
                  <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center">
                    <div className={`rounded-[14px] border p-6 ${result.passed ? "border-[#2f7770]/45 bg-[#2f7770]/12" : "border-[#823433]/45 bg-[#823433]/12"}`}>
                      <div className="text-xs font-bold uppercase tracking-[0.22em] text-[#70421f]">Result</div>
                      <h3 className="mt-3 text-4xl font-bold text-[#2f190b]">{result.passed ? "Passed" : "Needs more practice"}</h3>
                      <p className="mt-3 text-base leading-7 text-[#654223]">You scored <strong>{result.correct}/{result.total}</strong>.{payload?.track === "citizenship" ? ` Danish Values: ${result.valuesCorrect}/${result.valuesTotal}.` : ""}</p>
                      <div className="mt-5 grid gap-3 sm:grid-cols-2">
                        <ScoreLine label="Overall requirement" passed={result.totalPassed} text={`${blueprint?.passingScore}/${blueprint?.totalQuestions}`} />
                        {payload?.track === "citizenship" ? <ScoreLine label="Danish Values rule" passed={result.valuesPassed} text="4/5" /> : null}
                      </div>
                      <div className="mt-6 flex flex-wrap gap-3">
                        <button type="button" onClick={restart} className="inline-flex h-11 items-center gap-2 rounded-[8px] bg-[#72401f] px-4 text-sm font-bold text-[#f7ead4]"><RotateCcw size={16} aria-hidden />New paper</button>
                        <button type="button" onClick={() => setCurrentIndex(0)} className="inline-flex h-11 items-center gap-2 rounded-[8px] border border-[#70421f]/35 px-4 text-sm font-bold text-[#4b2a14]">Review answers</button>
                      </div>
                      {error ? <p className="mt-4 text-sm font-semibold text-[#823433]">{error}</p> : null}
                    </div>
                    <QuestionReview questions={questions} answers={answers} />
                  </div>
                ) : current ? (
                  <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center">
                    <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[#70421f]">
                      <span>{sectionLabels[current.section]}</span>
                      <span className="h-1 w-1 rounded-full bg-[#70421f]/50" />
                      <span>{current.source === "ai" ? "AI generated" : current.source === "current_affairs" ? "Current affairs" : "Official source"}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[#654223]">{sectionDescriptions[current.section]}</p>
                    <h3 data-preserve-language className="practice-question mt-7 text-3xl font-bold leading-tight">{current.stem}</h3>

                    <div className="mt-8 grid gap-3">
                      {current.choices.map((choice) => {
                        const chosen = selected === choice.key;
                        return (
                          <button key={choice.key} type="button" onClick={() => answer(choice.key)} className={`group grid grid-cols-[42px_1fr] items-center gap-3 rounded-[10px] border p-4 text-left transition ${chosen ? "border-[#70421f] bg-[#70421f]/16" : "border-[#946333]/45 bg-[#efe0bf]/65 hover:border-[#70421f] hover:bg-[#efe0bf]"}`}>
                            <span className="flex h-9 w-9 items-center justify-center rounded-full border border-[#70421f]/35 text-sm font-bold text-[#4b2a14]">{choice.key}</span>
                            <span data-preserve-language className="text-base font-semibold leading-7 text-[#3a210f]">{choice.text}</span>
                          </button>
                        );
                      })}
                    </div>

                    <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
                      <button type="button" onClick={() => goTo(currentIndex - 1)} disabled={currentIndex === 0} className="h-11 rounded-[8px] border border-[#70421f]/35 px-4 text-sm font-bold text-[#4b2a14] disabled:opacity-40">Previous</button>
                      {currentIndex + 1 === questions.length ? (
                        <button type="button" onClick={finishExam} className="inline-flex h-11 items-center gap-2 rounded-[8px] bg-[#72401f] px-4 text-sm font-bold text-[#f7ead4]"><Send size={16} aria-hidden />Submit exam</button>
                      ) : (
                        <button type="button" onClick={() => goTo(currentIndex + 1)} className="h-11 rounded-[8px] bg-[#72401f] px-4 text-sm font-bold text-[#f7ead4]">Next question</button>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
            </main>

            <aside className="min-h-[760px] border-l border-[#70421f]/35 bg-[#c9a777] p-5 text-[#2b180c] shadow-[inset_24px_0_38px_rgba(74,39,18,0.14)]">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.22em] text-[#70421f]"><NotebookPen size={15} aria-hidden />Exam notes</div>
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Private scratch notes for this paper..." className="mt-4 min-h-[190px] w-full resize-none rounded-[10px] border border-[#70421f]/35 bg-[#f0dfbd]/70 p-4 text-sm leading-6 text-[#2b180c] outline-none placeholder:text-[#7b5636]/70 focus:border-[#70421f]" />
              <button type="button" onClick={() => setNotes("")} className="mt-3 h-9 rounded-[8px] border border-[#70421f]/35 px-3 text-xs font-bold text-[#4b2a14] hover:bg-[#70421f]/10">Clear notes</button>

              <div className="mt-7 grid gap-2">
                {questions.map((question, index) => {
                  const answered = Boolean(answers[question.id]);
                  const active = index === currentIndex;
                  return (
                    <button key={question.id} type="button" onClick={() => goTo(index)} title={`${index + 1}. ${sectionLabels[question.section]}`} aria-label={`Question ${index + 1}: ${sectionLabels[question.section]}`} className={`flex items-center justify-between rounded-[8px] border px-3 py-2 text-left text-xs font-bold transition ${active ? "border-[#5e331a] bg-[#5e331a] text-[#f7ead4]" : answered ? "border-[#2f7770]/35 bg-[#2f7770]/12 text-[#2b180c]" : "border-[#946333]/35 bg-[#ead6b2]/55 text-[#4b2a14]"}`}>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      {answered ? <CheckCircle2 size={14} aria-hidden /> : null}
                    </button>
                  );
                })}
              </div>
            </aside>
          </div>
        </div>
      </section>
    </div>
  );
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex flex-1 items-center justify-center rounded-[12px] border border-[#946333]/40 bg-[#efe0bf]/55 p-8 text-center">
      <div>
        <div className="text-2xl font-bold text-[#2f190b]">{title}</div>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-[#654223]">{detail}</p>
      </div>
    </div>
  );
}

function ScoreLine({ label, text, passed }: { label: string; text: string; passed: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-[10px] border border-[#946333]/35 bg-[#efe0bf]/55 p-3 text-sm text-[#4b2a14]">
      <span>{label}</span>
      <strong className={passed ? "text-[#2f7770]" : "text-[#823433]"}>{passed ? "Met" : "Missed"} · {text}</strong>
    </div>
  );
}

function QuestionReview({ questions, answers }: { questions: MockQuestion[]; answers: Record<string, ChoiceKey> }) {
  return (
    <div className="mt-6 grid gap-3">
      {questions.map((question, index) => {
        const selected = answers[question.id];
        const correct = selected === question.correct_choice;
        return (
          <div key={question.id} className="rounded-[10px] border border-[#946333]/35 bg-[#efe0bf]/55 p-4">
            <div className="flex items-start justify-between gap-3 text-sm font-bold text-[#2f190b]"><span>{index + 1}. {question.stem}</span>{correct ? <CheckCircle2 className="shrink-0 text-[#2f7770]" size={18} aria-hidden /> : <XCircle className="shrink-0 text-[#823433]" size={18} aria-hidden />}</div>
            <p className="mt-2 text-xs text-[#654223]">Your answer: {selected ?? "None"} · Correct answer: {question.correct_choice}</p>
          </div>
        );
      })}
    </div>
  );
}

function shortSection(section: SectionKey) {
  if (section === "current_affairs") return "Current";
  if (section === "danish_values") return "Values";
  return "Knowledge";
}

