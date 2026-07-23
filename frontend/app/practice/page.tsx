"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, CheckCircle2, ChevronRight, RotateCcw, XCircle } from "lucide-react";
import { saveAttempt, saveLearningState } from "@/lib/progress-client";

type TrackKey = "pr" | "citizenship";
type ChoiceKey = "A" | "B" | "C";

type OfficialQuestion = {
  id: string;
  track: TrackKey;
  paper_code?: string;
  question_number?: number;
  stem: string;
  choice_a: string;
  choice_b: string;
  choice_c: string;
  correct_choice: ChoiceKey;
};

type PracticeState = "idle" | "loading" | "ready" | "answered" | "complete" | "error";

const trackLabels: Record<TrackKey, string> = {
  pr: "Permanent Residence",
  citizenship: "Citizenship"
};

function shuffle<T>(items: T[]) {
  return [...items]
    .map((item) => ({ item, sort: Math.random() }))
    .sort((a, b) => a.sort - b.sort)
    .map(({ item }) => item);
}

function seenKey(track: TrackKey) {
  return `denmark-academy-seen-past-paper-${track}`;
}

export default function PracticePage() {
  const [track, setTrack] = useState<TrackKey>("citizenship");
  const [state, setState] = useState<PracticeState>("idle");
  const [questions, setQuestions] = useState<OfficialQuestion[]>([]);
  const [deck, setDeck] = useState<OfficialQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selected, setSelected] = useState<ChoiceKey | null>(null);
  const [error, setError] = useState("");
  const [score, setScore] = useState({ correct: 0, answered: 0 });
  const [seenCount, setSeenCount] = useState(0);
  const initializedFromUrl = useRef(false);

  const current = deck[currentIndex];
  const progress = questions.length ? (Math.min(seenCount + 1, questions.length) + " / " + questions.length) : "0 / 0";

  const choices = useMemo(() => {
    if (!current) return [];
    return [
      { key: "A" as ChoiceKey, text: current.choice_a },
      { key: "B" as ChoiceKey, text: current.choice_b },
      { key: "C" as ChoiceKey, text: current.choice_c }
    ].filter((choice) => choice.text && choice.text.trim().length > 0);
  }, [current]);

  useEffect(() => {
    if (!initializedFromUrl.current) {
      initializedFromUrl.current = true;
      const requested = new URLSearchParams(window.location.search).get("track");
      if ((requested === "pr" || requested === "citizenship") && requested !== track) {
        setTrack(requested);
        return;
      }
    }
    void loadQuestions(track);
  }, [track]);

  async function loadQuestions(nextTrack: TrackKey) {
    setState("loading");
    setError("");
    setSelected(null);
    setScore({ correct: 0, answered: 0 });
    setCurrentIndex(0);

    try {
      const response = await fetch(`/api/past-paper-practice?track=${nextTrack}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Could not load questions");

      const loaded = (payload.questions ?? []) as OfficialQuestion[];
      setQuestions(loaded);
      let remoteSeen: string[] = [];
      try {
        const history = await fetch(`/api/account/progress/attempts/seen?module=past_papers&track=${nextTrack}`, { cache: "no-store" });
        if (history.ok) remoteSeen = ((await history.json()).question_ids ?? []) as string[];
      } catch { /* local history remains available offline */ }
      buildDeck(nextTrack, loaded, remoteSeen);
    } catch (caught) {
      setQuestions([]);
      setDeck([]);
      setState("error");
      setError(caught instanceof Error ? caught.message : "Could not load questions");
    }
  }

  function buildDeck(nextTrack: TrackKey, source: OfficialQuestion[], remoteSeen: string[] = [], randomize = true) {
    const stored = window.localStorage.getItem(seenKey(nextTrack));
    const seen = new Set<string>([...(stored ? JSON.parse(stored) as string[] : []), ...remoteSeen]);
    let fresh = source.filter((question) => !seen.has(question.id));
    setSeenCount(Math.min(seen.size, source.length));

    setDeck(randomize ? shuffle(fresh) : fresh);
    setCurrentIndex(0);
    setSelected(null);
    if (fresh.length) {
      setState("ready");
    } else if (source.length && seen.size) {
      setState("complete");
    } else {
      setState("error");
      setError("No past-paper questions found for this exam track.");
    }
  }

  function selectTrack(nextTrack: TrackKey) {
    setTrack(nextTrack);
  }

  function answer(choice: ChoiceKey) {
    if (!current || selected) return;
    const isCorrect = choice === current.correct_choice;
    setSelected(choice);
    setScore((value) => ({ correct: value.correct + (isCorrect ? 1 : 0), answered: value.answered + 1 }));

    const stored = window.localStorage.getItem(seenKey(track));
    const seen = new Set<string>(stored ? JSON.parse(stored) as string[] : []);
    seen.add(current.id);
    const completedCount = Math.min(questions.length, seenCount + 1);
    setSeenCount(completedCount);
    window.localStorage.setItem(seenKey(track), JSON.stringify([...seen]));
    setState("answered");
    void saveAttempt({
      module: "past_papers", question_id: current.id, selected_choice: choice,
      correct_choice: current.correct_choice, is_correct: isCorrect, track,
      topic: current.paper_code ?? "Official past paper",
      client_attempt_id: `past:${track}:${current.id}`,
      metadata: { paper_code: current.paper_code, question_number: current.question_number }
    });
    void saveLearningState("past_papers", {
      state_key: track, route: `/practice?track=${track}`, entity_id: current.id,
      title: `${trackLabels[track]} past papers`,
      completion_percent: questions.length ? (completedCount / questions.length) * 100 : 0,
      completed: questions.length > 0 && completedCount >= questions.length,
      state: { track, next_question_index: completedCount, answered_question_id: current.id, completed_items: completedCount, total_items: questions.length }
    });
  }

  function nextQuestion() {
    setSelected(null);
    if (currentIndex + 1 < deck.length) {
      setCurrentIndex((value) => value + 1);
      setState("ready");
      return;
    }
    setState("complete");
  }

  async function resetSeen() {
    window.localStorage.removeItem(seenKey(track));
    await fetch(`/api/account/progress/attempts/seen?module=past_papers&track=${track}`, { method: "DELETE" });
    setScore({ correct: 0, answered: 0 });
    setSeenCount(0);
    void saveLearningState("past_papers", { state_key: track, route: "/practice?track=" + track, title: trackLabels[track] + " past papers", completion_percent: 0, state: { track, completed_items: 0, total_items: questions.length, next_question_index: 0 } });
    buildDeck(track, questions, [], false);
  }

  const isCorrect = selected && current ? selected === current.correct_choice : false;

  return (
    <div className="practice-page space-y-8 pb-6">
      <section className="motion-panel mx-auto max-w-5xl text-center">
        <div className="text-xs font-semibold uppercase tracking-[0.3em] text-brass/75">Past Paper Practice</div>
        <h1 className="aesthetic-serif-strong mt-3 text-5xl leading-tight sm:text-6xl">Practice from official past papers.</h1>
        <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-[#c8ad88]">Choose an exam track, answer random past-paper MCQs, and receive instant right-or-wrong feedback.</p>
      </section>

      <section className="motion-panel rounded-[18px] border border-[#6f4324]/60 bg-[radial-gradient(circle_at_50%_0%,rgba(214,168,79,0.18),transparent_28rem),linear-gradient(135deg,#2a150b,#120805)] p-3 shadow-[0_34px_150px_rgba(0,0,0,0.5)] sm:p-5">
        <div className="rounded-[14px] border border-black/40 bg-[#2a160c] p-2 shadow-[inset_0_0_0_1px_rgba(255,226,168,0.08)]">
          <div className="grid overflow-hidden rounded-[11px] bg-[#3a2112] shadow-[inset_0_0_38px_rgba(0,0,0,0.5)] lg:grid-cols-[320px_1fr]">
            <aside className="relative min-h-[700px] bg-[#d9bf91] p-6 text-[#2b180c] shadow-[inset_-28px_0_44px_rgba(74,39,18,0.2)]">
              <div className="absolute right-0 top-0 h-full w-6 bg-gradient-to-r from-transparent to-[#70421f]/30" />
              <div className="relative z-10">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]"><BookOpen size={15} aria-hidden />Choose paper track</div>
                <div className="mt-5 grid gap-3">
                  {(["pr", "citizenship"] as TrackKey[]).map((item) => (
                    <button key={item} type="button" onClick={() => selectTrack(item)} className={`practice-track-button ${item === track ? "is-selected" : ""} rounded-[8px] border px-4 py-4 text-left transition ${item === track ? "border-[#5e331a] bg-[#5e331a] text-[#f7ead4] shadow-[0_14px_34px_rgba(80,39,16,0.28)]" : "border-[#946333]/50 bg-[#ead6b2]/70 text-[#4b2a14] hover:border-[#5e331a]"}`}>
                      <span className="practice-track-name block text-sm font-bold">{trackLabels[item]}</span>
                    </button>
                  ))}
                </div>

                <div className="mt-8 rounded-[10px] border border-[#946333]/45 bg-[#efe0bf]/60 p-4">
                  <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#70421f]">Session</div>
                  <div className="mt-3 grid gap-2 text-sm text-[#4b2a14]">
                    <div className="flex justify-between"><span>Remaining</span><strong>{deck.length ? Math.max(deck.length - currentIndex, 0) : 0}</strong></div>
                    <div className="flex justify-between"><span>Score</span><strong>{score.correct}/{score.answered}</strong></div>
                  </div>
                </div>

                <button type="button" onClick={resetSeen} className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-[8px] border border-[#70421f]/35 bg-transparent text-sm font-bold text-[#4b2a14] hover:bg-[#70421f]/10">
                  <RotateCcw size={15} aria-hidden />Start Again
                </button>
              </div>
            </aside>

            <main className="relative min-h-[700px] bg-[#ead6b2] p-5 text-[#2b180c] shadow-[inset_28px_0_44px_rgba(74,39,18,0.18)] sm:p-8">
              <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-[#70421f]/18 to-transparent" />
              <div className="relative z-10 flex min-h-full flex-col">
                <div className="mb-8 flex flex-wrap items-end justify-between gap-3 border-b border-[#9b7149]/25 pb-4">
                  <div>
                    <div className="text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]">{trackLabels[track]}</div>
                    <h2 className="mt-1 text-3xl font-bold tracking-tight text-[#3a210f]">Past paper MCQs</h2>
                  </div>
                  <div className="text-sm font-semibold text-[#7b5636]">{progress}</div>
                </div>

                {state === "loading" ? (
                  <div className="flex flex-1 items-center justify-center rounded-[12px] border border-[#946333]/40 bg-[#efe0bf]/55 text-lg font-semibold text-[#70421f]">Loading official questions...</div>
                ) : state === "complete" ? (
                  <div className="flex flex-1 items-center justify-center rounded-[12px] border border-[#946333]/40 bg-[#efe0bf]/55 p-8 text-center">
                    <div>
                      <CheckCircle2 size={48} className="mx-auto text-[#2f7770]" aria-hidden />
                      <div className="mt-4 text-xl font-bold text-[#2f190b]">All questions completed</div>
                      <p className="mt-2 text-sm leading-6 text-[#654223]">You have completed every Past Paper question in this section.</p>
                      <button type="button" onClick={resetSeen} className="mt-5 inline-flex h-11 items-center gap-2 rounded-[8px] bg-[#72401f] px-4 text-sm font-bold text-[#f7ead4]">
                        <RotateCcw size={15} aria-hidden />Start Again
                      </button>
                    </div>
                  </div>
                ) : state === "error" ? (
                  <div className="flex flex-1 items-center justify-center rounded-[12px] border border-[#946333]/40 bg-[#efe0bf]/55 p-8 text-center text-lg font-semibold text-[#70421f]">{error}</div>
                ) : current ? (
                  <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center">
                    <h3 data-preserve-language className="practice-question mt-5 text-3xl font-bold leading-tight">{current.stem}</h3>

                    <div className="mt-8 grid gap-3">
                      {choices.map((choice) => {
                        const chosen = selected === choice.key;
                        const correct = current.correct_choice === choice.key;
                        const showCorrect = selected && correct;
                        const showWrong = selected && chosen && !correct;
                        return (
                          <button key={choice.key} type="button" onClick={() => answer(choice.key)} disabled={Boolean(selected)} className={`group grid grid-cols-[42px_1fr_auto] items-center gap-3 rounded-[10px] border p-4 text-left transition ${showCorrect ? "border-[#2f7770] bg-[#2f7770]/18" : showWrong ? "border-[#823433] bg-[#823433]/15" : "border-[#946333]/45 bg-[#efe0bf]/65 hover:border-[#70421f] hover:bg-[#efe0bf]"}`}>
                            <span className="flex h-9 w-9 items-center justify-center rounded-full border border-[#70421f]/35 text-sm font-bold text-[#4b2a14]">{choice.key}</span>
                            <span data-preserve-language className="text-base font-semibold leading-7 text-[#3a210f]">{choice.text}</span>
                            {showCorrect ? <CheckCircle2 className="text-[#2f7770]" size={20} aria-hidden /> : showWrong ? <XCircle className="text-[#823433]" size={20} aria-hidden /> : null}
                          </button>
                        );
                      })}
                    </div>

                    {selected ? (
                      <div className={`mt-7 rounded-[10px] border p-4 ${isCorrect ? "border-[#2f7770]/45 bg-[#2f7770]/12" : "border-[#823433]/45 bg-[#823433]/12"}`}>
                        <div className="text-lg font-bold text-[#2f190b]">{isCorrect ? "Correct answer." : "Wrong answer."}</div>
                        <p className="mt-2 text-sm leading-6 text-[#654223]">The correct option is <strong>{current.correct_choice}</strong>.</p>
                      </div>
                    ) : null}

                    <div className="mt-7 flex justify-end">
                      <button type="button" onClick={nextQuestion} disabled={!selected} className="inline-flex h-11 items-center gap-2 rounded-[8px] bg-[#72401f] px-4 text-sm font-bold text-[#f7ead4] disabled:cursor-not-allowed disabled:opacity-45">
                        Next question <ChevronRight size={16} aria-hidden />
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



