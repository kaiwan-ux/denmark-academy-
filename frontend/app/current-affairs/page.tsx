"use client";

import { useEffect, useMemo, useState } from "react";
import { Newspaper, CheckCircle2, ChevronRight, RotateCcw, XCircle } from "lucide-react";
import { saveAttempt, saveLearningState } from "@/lib/progress-client";

type TrackKey = "pr" | "citizenship" | "both";
type ChoiceKey = "a" | "b" | "c";
type DifficultyLevel = "easy" | "medium" | "hard";

type Question = {
  id: string;
  question_stem: string;
  choice_a: string;
  choice_b: string;
  choice_c: string;
  topic: string | null;
  difficulty: string;
  article_title: string;
  article_url: string;
};

type SessionState = "config" | "loading" | "ready" | "answered" | "error";

const trackLabels: Record<TrackKey, string> = {
  pr: "Permanent Residence",
  citizenship: "Citizenship",
  both: "Both"
};

const CURRENT_AFFAIRS_SEEN_KEY = "denmark-academy-current-affairs-seen";

function locallySeenQuestionIds(): string[] {
  try {
    const value = JSON.parse(window.localStorage.getItem(CURRENT_AFFAIRS_SEEN_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function rememberQuestionLocally(questionId: string) {
  const next = Array.from(new Set([...locallySeenQuestionIds(), questionId])).slice(-1000);
  window.localStorage.setItem(CURRENT_AFFAIRS_SEEN_KEY, JSON.stringify(next));
}
const difficultyLabels: Record<DifficultyLevel, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard"
};

export default function CurrentAffairsPage() {
  const [track, setTrack] = useState<TrackKey>("both");
  const [difficulty, setDifficulty] = useState<DifficultyLevel | null>(null);
  const [questionCount, setQuestionCount] = useState<number>(10);
  const [state, setState] = useState<SessionState>("config");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selected, setSelected] = useState<ChoiceKey | null>(null);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [score, setScore] = useState({ correct: 0, answered: 0 });
  const [poolTotal, setPoolTotal] = useState(0);
  const [completedBefore, setCompletedBefore] = useState(0);
  const [answerResult, setAnswerResult] = useState<{
    is_correct: boolean;
    correct_choice: string;
    explanation: string;
  } | null>(null);

  useEffect(() => {
        fetch("/api/account/progress/states/current_affairs?state_key=all", { cache: "no-store" })
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => {
        const saved = payload?.state?.state;
        if (!saved?.questions?.length || !saved?.session_id || Number(saved.score?.answered ?? 0) >= saved.questions.length) return;
        setQuestions(saved.questions as Question[]);
        setSessionId(saved.session_id);
        setTrack(saved.track as TrackKey);
        setDifficulty(saved.difficulty as DifficultyLevel | null);
        setCurrentIndex(Math.min(Number(saved.next_index ?? 0), saved.questions.length - 1));
        setScore(saved.score ?? { correct: 0, answered: 0 });
        setCompletedBefore(Math.max(0, Number(saved.completed_items ?? 0) - Number(saved.score?.answered ?? 0)));
        setPoolTotal(Number(saved.total_items ?? saved.questions.length));
        setState("ready");
      }).catch(() => undefined);
  }, []);
  const current = questions[currentIndex];
  const progress = poolTotal ? (Math.min(completedBefore + score.answered + 1, poolTotal) + " / " + poolTotal) : (questions.length ? (Math.min(currentIndex + 1, questions.length) + " / " + questions.length) : "0 / 0");

  const choices = useMemo(() => {
    if (!current) return [];
    return [
      { key: "a" as ChoiceKey, text: current.choice_a },
      { key: "b" as ChoiceKey, text: current.choice_b },
      { key: "c" as ChoiceKey, text: current.choice_c }
    ].filter((choice) => choice.text && choice.text.trim().length > 0);
  }, [current]);

  async function startSession() {
    setState("loading");
    setError("");
    setSelected(null);
    setScore({ correct: 0, answered: 0 });
    setCurrentIndex(0);
    setAnswerResult(null);

    try {
      let seenIds: string[] = locallySeenQuestionIds();
      try {
        const seenResponse = await fetch("/api/account/progress/attempts/seen?module=current_affairs", { cache: "no-store" });
        if (seenResponse.ok) seenIds = Array.from(new Set([...seenIds, ...((await seenResponse.json()).question_ids ?? [])]));
      } catch { /* use the available grounded pool */ }
      const response = await fetch(`/api/current-affairs/practice`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ exam_type: "both", difficulty, count: questionCount, exclude_question_ids: seenIds, refresh_articles: true, article_count: 6 }),
        cache: "no-store"
      });

      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Could not start practice session");

      const loaded = (payload.questions ?? []) as Question[];
      
      if (loaded.length !== questionCount) {
        throw new Error(`The service prepared ${loaded.length} of ${questionCount} questions. Please retry after the news pool refreshes.`);
      }

      if (payload.cycle_reset) {
        seenIds = [];
        window.localStorage.removeItem(CURRENT_AFFAIRS_SEEN_KEY);
      }
      setPoolTotal(Number(payload.pool_total ?? loaded.length));
      setCompletedBefore(Math.min(
        Number(payload.served_before ?? seenIds.length),
        Number(payload.pool_total ?? loaded.length),
      ));
      setQuestions(loaded);
      setSessionId(payload.session_id);
      setCurrentIndex(0);
      setSelected(null);
      setState("ready");
    } catch (caught) {
      setQuestions([]);
      setState("error");
      setError(caught instanceof Error ? caught.message : "Could not load current affairs questions");
    }
  }

  async function answer(choice: ChoiceKey) {
    if (!current || selected || !sessionId) return;
    
    setSelected(choice);
    setState("loading");

    try {
      const response = await fetch(`/api/current-affairs/practice/${sessionId}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_id: current.id, user_choice: choice })
      });

      if (!response.ok) throw new Error("Failed to submit answer");

      const result = await response.json();
      setAnswerResult(result);
      
      const nextScore = { correct: score.correct + (result.is_correct ? 1 : 0), answered: score.answered + 1 };
      const completedCount = Math.min(poolTotal || questions.length, completedBefore + nextScore.answered);
      setScore(nextScore);
      setState("answered");
      await saveAttempt({
        module: "current_affairs", question_id: current.id, selected_choice: choice,
        correct_choice: result.correct_choice, is_correct: result.is_correct, track: "all",
        topic: current.topic ?? "Current Affairs", session_key: sessionId,
        client_attempt_id: "current:" + sessionId + ":" + current.id,
        metadata: { article_title: current.article_title, article_url: current.article_url }
      });
      rememberQuestionLocally(current.id);
      void saveLearningState("current_affairs", {
        state_key: "all", route: "/current-affairs", title: "Current Affairs", entity_id: current.id,
        completion_percent: poolTotal ? (completedCount / poolTotal) * 100 : 0,
        completed: poolTotal > 0 && completedCount >= poolTotal,
        state: {
          questions, session_id: sessionId, difficulty,
          next_index: Math.min(currentIndex + 1, questions.length - 1),
          score: nextScore, completed_items: completedCount, total_items: poolTotal || questions.length
        }
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to submit answer");
      setState("error");
    }
  }

  function nextQuestion() {
    setSelected(null);
    setAnswerResult(null);
    if (currentIndex + 1 < questions.length) {
      setCurrentIndex((value) => value + 1);
      setState("ready");
    } else {
      // Session complete
      completeSession();
    }
  }

  async function completeSession() {
    if (!sessionId) return;
    
    try {
      await fetch(`/api/current-affairs/practice/${sessionId}/complete`, {
        method: "POST"
      });
    } catch (err) {
      // Silent fail - session still complete locally
    }
    
    setState("config");
  }

  function resetSession() {
    setState("config");
    setQuestions([]);
    setCurrentIndex(0);
    setSelected(null);
    setScore({ correct: 0, answered: 0 });
    setError("");
    setSessionId(null);
    setAnswerResult(null);
  }

  const isCorrect = answerResult?.is_correct ?? false;
  const sessionComplete = state === "config" && score.answered > 0;

  return (
    <div className="practice-page current-affairs-page space-y-8 pb-6">
      <section className="motion-panel mx-auto max-w-5xl text-center">
        <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.3em] text-brass/75">
          <Newspaper size={14} aria-hidden />
          Current Affairs
        </div>
        <h1 className="aesthetic-serif-strong mt-3 text-5xl leading-tight sm:text-6xl">Real news, exam-style questions.</h1>
        <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-[#c8ad88]">Practice with multiple-choice questions generated from recent Danish news articles.</p>
      </section>

      <section className="motion-panel rounded-[18px] border border-[#6f4324]/60 bg-[radial-gradient(circle_at_50%_0%,rgba(214,168,79,0.18),transparent_28rem),linear-gradient(135deg,#2a150b,#120805)] p-3 shadow-[0_34px_150px_rgba(0,0,0,0.5)] sm:p-5">
        <div className="rounded-[14px] border border-black/40 bg-[#2a160c] p-2 shadow-[inset_0_0_0_1px_rgba(255,226,168,0.08)]">
          <div className="grid overflow-hidden rounded-[11px] bg-[#3a2112] shadow-[inset_0_0_38px_rgba(0,0,0,0.5)] lg:grid-cols-[320px_1fr]">
            <aside className="relative min-h-[700px] bg-[#d9bf91] p-6 text-[#2b180c] shadow-[inset_-28px_0_44px_rgba(74,39,18,0.2)]">
              <div className="absolute right-0 top-0 h-full w-6 bg-gradient-to-r from-transparent to-[#70421f]/30" />
              <div className="relative z-10">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]">
                  <Newspaper size={15} aria-hidden />
                  Configuration
                </div>

                {state === "config" && (
                  <>
                    <div className="mt-5">
                      <label className="block text-xs font-bold uppercase tracking-[0.18em] text-[#70421f]">Difficulty (Optional)</label>
                      <div className="mt-2 grid gap-2">
                        <button type="button" onClick={() => setDifficulty(null)} className={`rounded-[8px] border px-4 py-3 text-left transition ${difficulty === null ? "border-[#5e331a] bg-[#5e331a] text-[#f7ead4] shadow-[0_14px_34px_rgba(80,39,16,0.28)]" : "border-[#946333]/50 bg-[#ead6b2]/70 text-[#4b2a14] hover:border-[#5e331a]"}`}>
                          <span className="block text-sm font-bold">Any</span>
                        </button>
                        {(["easy", "medium", "hard"] as DifficultyLevel[]).map((level) => (
                          <button key={level} type="button" onClick={() => setDifficulty(level)} className={`rounded-[8px] border px-4 py-3 text-left transition ${level === difficulty ? "border-[#5e331a] bg-[#5e331a] text-[#f7ead4] shadow-[0_14px_34px_rgba(80,39,16,0.28)]" : "border-[#946333]/50 bg-[#ead6b2]/70 text-[#4b2a14] hover:border-[#5e331a]"}`}>
                            <span className="block text-sm font-bold">{difficultyLabels[level]}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="mt-5">
                      <label className="current-affairs-count-label">Number of Questions</label>
                      <input
                        type="number"
                        min="1"
                        max="20"
                        value={questionCount}
                        onChange={(e) => setQuestionCount(Math.min(20, Math.max(1, parseInt(e.target.value) || 10)))}
                        className="current-affairs-count-input"
                      />
                    </div>

                    <button type="button" onClick={startSession} className="mt-6 inline-flex h-12 w-full items-center justify-center gap-2 rounded-[8px] bg-[#5e331a] text-sm font-bold text-[#f7ead4] shadow-[0_14px_34px_rgba(80,39,16,0.28)] hover:bg-[#70421f]">
                      <Newspaper size={16} aria-hidden />
                      Load Questions
                    </button>

                    {sessionComplete && (
                      <div className="mt-5 rounded-[10px] border border-[#2f7770]/45 bg-[#2f7770]/12 p-4">
                        <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#2f7770]">Session Complete!</div>
                        <div className="mt-2 text-2xl font-bold text-[#2f190b]">{score.correct} / {score.answered}</div>
                        <div className="mt-1 text-sm text-[#654223]">Correct answers</div>
                      </div>
                    )}
                  </>
                )}

                {state !== "config" && (
                  <>
                    <div className="mt-5 rounded-[10px] border border-[#946333]/45 bg-[#efe0bf]/60 p-4">
                      <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#70421f]">Session</div>
                      <div className="mt-3 grid gap-2 text-sm text-[#4b2a14]">
                                                <div className="flex justify-between"><span>Difficulty</span><strong>{difficulty ? difficultyLabels[difficulty] : "Any"}</strong></div>
                        <div className="flex justify-between"><span>Questions</span><strong>{questions.length}</strong></div>
                        <div className="flex justify-between"><span>Score</span><strong>{score.correct}/{score.answered}</strong></div>
                      </div>
                    </div>

                    <button type="button" onClick={resetSession} className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-[8px] border border-[#70421f]/35 bg-transparent text-sm font-bold text-[#4b2a14] hover:bg-[#70421f]/10">
                      <RotateCcw size={15} aria-hidden />
                      New Session
                    </button>
                  </>
                )}
              </div>
            </aside>

            <main className="relative min-h-[700px] bg-[#ead6b2] p-5 text-[#2b180c] shadow-[inset_28px_0_44px_rgba(74,39,18,0.18)] sm:p-8">
              <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-[#70421f]/18 to-transparent" />
              <div className="relative z-10 flex min-h-full flex-col">
                <div className="mb-8 flex flex-wrap items-end justify-between gap-3 border-b border-[#9b7149]/25 pb-4">
                  <div>
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]">
                      <Newspaper size={14} aria-hidden />
                      Current Affairs
                    </div>
                    <h2 className="mt-1 text-3xl font-bold tracking-tight text-[#3a210f]">Current Affairs Questions</h2>
                  </div>
                  {state !== "config" && <div className="text-sm font-semibold text-[#7b5636]">{progress}</div>}
                </div>

                {state === "config" && !sessionComplete ? (
                  <div className="flex flex-1 items-center justify-center rounded-[12px] border border-[#946333]/40 bg-[#efe0bf]/55 p-8 text-center">
                    <div>
                      <Newspaper size={48} className="mx-auto text-[#70421f]" aria-hidden />
                      <div className="mt-4 text-lg font-semibold text-[#70421f]">Configure your session</div>
                      <div className="mt-2 text-sm text-[#654223]">Choose difficulty and how many fresh questions to generate from six recent Danish articles</div>
                    </div>
                  </div>
                ) : state === "loading" ? (
                  <div className="flex flex-1 items-center justify-center rounded-[12px] border border-[#946333]/40 bg-[#efe0bf]/55">
                    <div className="text-center">
                      <Newspaper size={48} className="mx-auto animate-pulse text-[#70421f]" aria-hidden />
                      <div className="mt-4 text-lg font-semibold text-[#70421f]">Loading questions...</div>
                      <div className="mt-2 text-sm text-[#654223]">Please wait</div>
                    </div>
                  </div>
                ) : state === "error" ? (
                  <div className="flex flex-1 items-center justify-center rounded-[12px] border border-[#823433]/45 bg-[#823433]/12 p-8 text-center">
                    <div>
                      <div className="text-lg font-semibold text-[#823433]">Loading Failed</div>
                      <div className="mt-2 text-sm text-[#654223]">{error}</div>
                      <button type="button" onClick={resetSession} className="mt-4 inline-flex h-10 items-center gap-2 rounded-[8px] border border-[#70421f]/35 bg-transparent px-4 text-sm font-bold text-[#4b2a14] hover:bg-[#70421f]/10">
                        <RotateCcw size={15} aria-hidden />
                        Try Again
                      </button>
                    </div>
                  </div>
                ) : current ? (
                  <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center">
                    <div className="mb-3 flex items-start gap-2 text-xs text-[#7b5636]">
                      <Newspaper size={14} className="mt-0.5 shrink-0" aria-hidden />
                      <a href={current.article_url} target="_blank" rel="noopener noreferrer" className="hover:text-[#5e331a] hover:underline">
                        <span data-preserve-language>{current.article_title}</span>
                      </a>
                    </div>
                    
                    <h3 data-preserve-language className="practice-question text-3xl font-bold leading-tight">{current.question_stem}</h3>

                    {current.topic && (
                      <div data-preserve-language className="mt-3 inline-block rounded-full bg-[#70421f]/15 px-3 py-1 text-xs font-semibold text-[#5e331a]">
                        {current.topic}
                      </div>
                    )}

                    <div className="mt-8 grid gap-3">
                      {choices.map((choice) => {
                        const chosen = selected === choice.key;
                        const correct = answerResult?.correct_choice === choice.key;
                        const showCorrect = answerResult && correct;
                        const showWrong = answerResult && chosen && !correct;
                        return (
                          <button key={choice.key} type="button" onClick={() => answer(choice.key)} disabled={Boolean(selected) || state !== "ready"} className={`group grid grid-cols-[42px_1fr_auto] items-center gap-3 rounded-[10px] border p-4 text-left transition ${showCorrect ? "border-[#2f7770] bg-[#2f7770]/18" : showWrong ? "border-[#823433] bg-[#823433]/15" : "border-[#946333]/45 bg-[#efe0bf]/65 hover:border-[#70421f] hover:bg-[#efe0bf] disabled:opacity-50 disabled:cursor-not-allowed"}`}>
                            <span className="flex h-9 w-9 items-center justify-center rounded-full border border-[#70421f]/35 text-sm font-bold text-[#4b2a14] uppercase">{choice.key}</span>
                            <span data-preserve-language className="text-base font-semibold leading-7 text-[#3a210f]">{choice.text}</span>
                            {showCorrect ? <CheckCircle2 className="text-[#2f7770]" size={20} aria-hidden /> : showWrong ? <XCircle className="text-[#823433]" size={20} aria-hidden /> : null}
                          </button>
                        );
                      })}
                    </div>

                    {answerResult ? (
                      <div className={`mt-7 rounded-[10px] border p-4 ${isCorrect ? "border-[#2f7770]/45 bg-[#2f7770]/12" : "border-[#823433]/45 bg-[#823433]/12"}`}>
                        <div className="text-lg font-bold text-[#2f190b]">{isCorrect ? "Correct answer." : "Wrong answer."}</div>
                        <p className="mt-2 text-sm leading-6 text-[#654223]">The correct option is <strong className="uppercase">{answerResult.correct_choice}</strong>.</p>
                        {answerResult.explanation && (
                          <p data-preserve-language className="mt-3 text-sm leading-6 italic text-[#654223]">{answerResult.explanation}</p>
                        )}
                      </div>
                    ) : null}

                    <div className="mt-7 flex justify-end">
                      <button type="button" onClick={nextQuestion} disabled={!answerResult} className="inline-flex h-11 items-center gap-2 rounded-[8px] bg-[#72401f] px-4 text-sm font-bold text-[#f7ead4] disabled:cursor-not-allowed disabled:opacity-45">
                        {currentIndex + 1 < questions.length ? "Next question" : "Finish session"} <ChevronRight size={16} aria-hidden />
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            </main>
          </div>
        </div>
      </section>
    </div>
  );
}






