"use client";

import "./chapter-practice.css";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpenCheck,
  CheckCircle2,
  ChevronRight,
  ListOrdered,
  LoaderCircle,
  RefreshCcw,
  Shuffle,
  XCircle,
} from "lucide-react";
import { useLanguage } from "@/components/language-provider";
import { saveLearningState } from "@/lib/progress-client";

type Track = "citizenship" | "pr";
type Mode = "sequential" | "random";
type Choice = "A" | "B" | "C";
type Screen = "config" | "loading" | "practice" | "complete" | "error";

type Chapter = {
  chapter_number: number;
  title: string;
  question_count: number;
  completed_questions: number;
  total_attempts: number;
  correct_attempts: number;
  accuracy: number;
  completion_percent: number;
};

type PracticeQuestion = {
  id: string;
  question_number: number;
  stem: string;
  choice_a: string;
  choice_b: string;
  choice_c: string;
};

type PracticeSession = {
  session_id: string;
  track: Track;
  chapter_number: number;
  chapter_title: string;
  mode: Mode;
  questions: PracticeQuestion[];
  count: number;
};

type Feedback = {
  is_correct: boolean;
  selected_choice: Choice;
  correct_choice: Choice;
  correct_text: string;
};

const labels = {
  da: {
    eyebrow: "KAPITELTRÆNING",
    title: "Øv ét kapitel ad gangen.",
    description: "Vælg et kapitel, arbejd fra et bestemt spørgsmål til et andet, eller få et tilfældigt udvalg. Facit vises først, når du har svaret.",
    track: "PRØVETYPE",
    citizenship: "Indfødsret",
    pr: "Permanent ophold",
    chapters: "KAPITLER",
    completed: "gennemført",
    attempted: "forsøg",
    accuracy: "korrekt",
    loadingChapters: "Henter kapitler...",
    chooseChapter: "Vælg et kapitel",
    chooseChapterHelp: "Din træning og fremgang gemmes automatisk på din konto.",
    method: "Vælg rækkefølge",
    sequential: "Fra nummer til nummer",
    sequentialHelp: "Arbejd i bogens rækkefølge.",
    random: "Tilfældige spørgsmål",
    randomHelp: "Få et nyt blandet udvalg fra kapitlet.",
    from: "Fra spørgsmål",
    to: "Til spørgsmål",
    number: "Antal spørgsmål",
    start: "Start kapiteltræning",
    preparing: "Forbereder spørgsmål...",
    question: "Spørgsmål",
    of: "af",
    correct: "Korrekt svar",
    wrong: "Ikke korrekt",
    answer: "Facit",
    next: "Næste spørgsmål",
    finish: "Se resultat",
    result: "Kapitlet er gennemført",
    resultText: "Dine svar er gemt. Du kan vælge en ny del af kapitlet eller øve et andet kapitel.",
    newSession: "Vælg ny træning",
    score: "korrekte svar",
    retry: "Prøv igen",
    loadError: "Kapitlerne kunne ikke hentes.",
    sessionError: "Træningen kunne ikke startes.",
  },
  en: {
    eyebrow: "CHAPTER PRACTICE",
    title: "Master one chapter at a time.",
    description: "Choose a chapter, practise a numbered range, or receive a random selection. The verified answer appears only after you respond.",
    track: "EXAM TRACK",
    citizenship: "Citizenship",
    pr: "Permanent Residence",
    chapters: "CHAPTERS",
    completed: "completed",
    attempted: "attempts",
    accuracy: "accuracy",
    loadingChapters: "Loading chapters...",
    chooseChapter: "Choose a chapter",
    chooseChapterHelp: "Your practice and progress are saved automatically to your account.",
    method: "Choose question order",
    sequential: "From number to number",
    sequentialHelp: "Work in the chapter's original order.",
    random: "Random questions",
    randomHelp: "Receive a newly shuffled selection from the chapter.",
    from: "From question",
    to: "To question",
    number: "Number of questions",
    start: "Start chapter practice",
    preparing: "Preparing questions...",
    question: "Question",
    of: "of",
    correct: "Correct answer",
    wrong: "Not correct",
    answer: "Answer",
    next: "Next question",
    finish: "View result",
    result: "Chapter session completed",
    resultText: "Your answers are saved. You can choose another part of this chapter or practise a different chapter.",
    newSession: "Choose new practice",
    score: "correct answers",
    retry: "Try again",
    loadError: "The chapters could not be loaded.",
    sessionError: "The practice session could not be started.",
  },
};

function chapterStateKey(track: Track) {
  return track;
}

export default function ChapterPracticePage() {
  const { language } = useLanguage();
  const text = labels[language];
  const [track, setTrack] = useState<Track>("citizenship");
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chaptersLoading, setChaptersLoading] = useState(true);
  const [chapterNumber, setChapterNumber] = useState(1);
  const [mode, setMode] = useState<Mode>("sequential");
  const [startNumber, setStartNumber] = useState(1);
  const [endNumber, setEndNumber] = useState(10);
  const [randomCount, setRandomCount] = useState(10);
  const [screen, setScreen] = useState<Screen>("config");
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const selectedChapter = useMemo(
    () => chapters.find((chapter) => chapter.chapter_number === chapterNumber) ?? chapters[0],
    [chapterNumber, chapters],
  );
  const currentQuestion = session?.questions[currentIndex];
  const currentFeedback = currentQuestion ? feedback[currentQuestion.id] : undefined;
  const correctCount = Object.values(feedback).filter((item) => item.is_correct).length;

  const loadChapters = useCallback(async (requestedTrack: Track, preferredChapter?: number) => {
    setChaptersLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/chapter-practice/chapters?track=${requestedTrack}`, { cache: "no-store" });
      if (response.status === 401) {
        window.location.assign(`/login?returnTo=${encodeURIComponent(`/revision?track=${requestedTrack}`)}`);
        return;
      }
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || text.loadError);
      const loaded = (payload.chapters ?? []) as Chapter[];
      setChapters(loaded);
      const candidate = preferredChapter ?? chapterNumber;
      const nextChapter = loaded.some((item) => item.chapter_number === candidate)
        ? candidate
        : loaded[0]?.chapter_number ?? 1;
      setChapterNumber(nextChapter);
      const total = loaded.find((item) => item.chapter_number === nextChapter)?.question_count ?? 10;
      setStartNumber(1);
      setEndNumber(Math.min(10, total));
      setRandomCount(Math.min(10, total));
    } catch (caught) {
      setChapters([]);
      setError(caught instanceof Error ? caught.message : text.loadError);
    } finally {
      setChaptersLoading(false);
    }
  }, [chapterNumber, text.loadError]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedTrack: Track = params.get("track") === "pr" ? "pr" : "citizenship";
    const requestedChapter = Number(params.get("chapter") || 1);
    setTrack(requestedTrack);
    void loadChapters(requestedTrack, requestedChapter);
  // The initial URL must be read once; later track changes are handled explicitly.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function chooseTrack(nextTrack: Track) {
    if (nextTrack === track) return;
    setTrack(nextTrack);
    setSession(null);
    setFeedback({});
    setScreen("config");
    window.history.replaceState(null, "", `/revision?track=${nextTrack}`);
    void loadChapters(nextTrack, 1);
  }

  function chooseChapter(nextChapter: Chapter) {
    setSession(null);
    setFeedback({});
    setCurrentIndex(0);
    setError("");
    setScreen("config");
    setChapterNumber(nextChapter.chapter_number);
    setStartNumber(1);
    setEndNumber(Math.min(10, nextChapter.question_count));
    setRandomCount(Math.min(10, nextChapter.question_count));
    window.history.replaceState(null, "", `/revision?track=${track}&chapter=${nextChapter.chapter_number}`);
  }

  async function startSession() {
    if (!selectedChapter) return;
    setScreen("loading");
    setError("");
    setFeedback({});
    setCurrentIndex(0);
    try {
      const requestBody = mode === "sequential"
        ? { track, chapter_number: selectedChapter.chapter_number, mode, start_number: startNumber, end_number: endNumber }
        : { track, chapter_number: selectedChapter.chapter_number, mode, count: randomCount };
      const response = await fetch("/api/chapter-practice/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(requestBody),
        cache: "no-store",
      });
      if (response.status === 401) {
        window.location.assign(`/login?returnTo=${encodeURIComponent(`/revision?track=${track}&chapter=${selectedChapter.chapter_number}`)}`);
        return;
      }
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || text.sessionError);
      const nextSession = payload as PracticeSession;
      setSession(nextSession);
      setScreen("practice");
      void saveLearningState("chapter_practice", {
        state_key: chapterStateKey(track),
        route: `/revision?track=${track}&chapter=${selectedChapter.chapter_number}`,
        entity_id: `chapter:${track}:${selectedChapter.chapter_number}:${nextSession.questions[0]?.question_number ?? 1}`,
        title: `${track === "citizenship" ? "Citizenship" : "Permanent Residence"} chapter practice`,
        completion_percent: selectedChapter.completion_percent,
        state: {
          kind: "chapter_practice",
          session: nextSession,
          current_index: 0,
          feedback: {},
          completed_items: selectedChapter.completed_questions,
          total_items: track === "citizenship" ? 600 : 780,
        },
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : text.sessionError);
      setScreen("error");
    }
  }

  async function answerQuestion(choice: Choice) {
    if (!session || !currentQuestion || currentFeedback || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch("/api/chapter-practice/answers", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ session_id: session.session_id, question_id: currentQuestion.id, selected_choice: choice }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || text.sessionError);
      const nextFeedback = { ...feedback, [currentQuestion.id]: payload as Feedback };
      setFeedback(nextFeedback);
      const trackProgress = payload.track_progress ?? {};
      void saveLearningState("chapter_practice", {
        state_key: chapterStateKey(track),
        route: `/revision?track=${track}&chapter=${session.chapter_number}`,
        entity_id: `chapter:${track}:${session.chapter_number}:${currentQuestion.question_number}`,
        title: `${track === "citizenship" ? "Citizenship" : "Permanent Residence"} chapter practice`,
        completion_percent: trackProgress.total_items
          ? (Number(trackProgress.completed_items || 0) / Number(trackProgress.total_items)) * 100
          : 0,
        state: {
          kind: "chapter_practice",
          session,
          current_index: currentIndex,
          feedback: nextFeedback,
          completed_items: Number(trackProgress.completed_items || 0),
          total_items: Number(trackProgress.total_items || (track === "citizenship" ? 600 : 780)),
        },
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : text.sessionError);
    } finally {
      setSubmitting(false);
    }
  }

  function nextQuestion() {
    if (!session) return;
    if (currentIndex + 1 >= session.questions.length) {
      setScreen("complete");
      void loadChapters(track, session.chapter_number);
      return;
    }
    const nextIndex = currentIndex + 1;
    setCurrentIndex(nextIndex);
    const nextQuestion = session.questions[nextIndex];
    void saveLearningState("chapter_practice", {
      state_key: chapterStateKey(track),
      route: `/revision?track=${track}&chapter=${session.chapter_number}`,
      entity_id: `chapter:${track}:${session.chapter_number}:${nextQuestion.question_number}`,
      title: `${track === "citizenship" ? "Citizenship" : "Permanent Residence"} chapter practice`,
      state: { kind: "chapter_practice", session, current_index: nextIndex, feedback },
    });
  }

  function resetConfiguration() {
    setSession(null);
    setFeedback({});
    setCurrentIndex(0);
    setError("");
    setScreen("config");
  }

  const choices = currentQuestion
    ? (["A", "B", "C"] as Choice[]).map((key) => ({
        key,
        text: currentQuestion[`choice_${key.toLowerCase()}` as "choice_a" | "choice_b" | "choice_c"],
      }))
    : [];

  return (
    <div className="chapter-practice-page" data-preserve-language>
      <section className="chapter-practice-hero">
        <div className="chapter-practice-eyebrow"><BookOpenCheck size={16} aria-hidden />{text.eyebrow}</div>
        <h1>{text.title}</h1>
        <p>{text.description}</p>
      </section>

      <section className="chapter-practice-shell">
        <aside className="chapter-practice-sidebar">
          <div className="chapter-practice-section-label">{text.track}</div>
          <div className="chapter-track-switch">
            <button type="button" className={track === "citizenship" ? "active" : ""} onClick={() => chooseTrack("citizenship")}>{text.citizenship}</button>
            <button type="button" className={track === "pr" ? "active" : ""} onClick={() => chooseTrack("pr")}>{text.pr}</button>
          </div>

          <div className="chapter-practice-section-label chapter-list-label">{text.chapters}</div>
          {chaptersLoading ? (
            <div className="chapter-loading"><LoaderCircle className="animate-spin" size={18} />{text.loadingChapters}</div>
          ) : (
            <div className="chapter-list">
              {chapters.map((chapter) => (
                <button key={chapter.chapter_number} type="button" className={chapter.chapter_number === chapterNumber ? "active" : ""} onClick={() => chooseChapter(chapter)}>
                  <span className="chapter-number">{String(chapter.chapter_number).padStart(2, "0")}</span>
                  <span className="chapter-list-copy"><strong>{chapter.title}</strong><small>{chapter.completed_questions}/{chapter.question_count} {text.completed}</small></span>
                  <span className="chapter-list-percent">{Math.round(chapter.completion_percent)}%</span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <div className="chapter-practice-main">
          <div className="chapter-practice-header">
            <div><span>{track === "citizenship" ? text.citizenship : text.pr}</span><h2>{selectedChapter ? `${selectedChapter.chapter_number}. ${selectedChapter.title}` : text.chooseChapter}</h2></div>
            {selectedChapter ? <div className="chapter-header-progress"><strong>{selectedChapter.completed_questions}/{selectedChapter.question_count}</strong><span>{text.completed}</span></div> : null}
          </div>

          {error && screen !== "error" ? <div className="chapter-inline-error" role="alert">{error}</div> : null}

          {screen === "config" ? (
            <div className="chapter-config">
              <div className="chapter-intro-card"><BookOpenCheck size={32} /><div><h3>{text.chooseChapter}</h3><p>{text.chooseChapterHelp}</p></div></div>
              {selectedChapter ? (
                <>
                  <div className="chapter-stats-row">
                    <article><strong>{selectedChapter.question_count}</strong><span>{text.question}</span></article>
                    <article><strong>{selectedChapter.total_attempts}</strong><span>{text.attempted}</span></article>
                    <article><strong>{selectedChapter.accuracy}%</strong><span>{text.accuracy}</span></article>
                  </div>
                  <div className="chapter-method-title">{text.method}</div>
                  <div className="chapter-mode-grid">
                    <button type="button" className={mode === "sequential" ? "active" : ""} onClick={() => setMode("sequential")}><ListOrdered /><span><strong>{text.sequential}</strong><small>{text.sequentialHelp}</small></span></button>
                    <button type="button" className={mode === "random" ? "active" : ""} onClick={() => setMode("random")}><Shuffle /><span><strong>{text.random}</strong><small>{text.randomHelp}</small></span></button>
                  </div>
                  {mode === "sequential" ? (
                    <div className="chapter-range-grid">
                      <label><span>{text.from}</span><input type="number" min={1} max={selectedChapter.question_count} value={startNumber} onChange={(event) => setStartNumber(Math.min(selectedChapter.question_count, Math.max(1, Number(event.target.value) || 1)))} /></label>
                      <label><span>{text.to}</span><input type="number" min={startNumber} max={selectedChapter.question_count} value={endNumber} onChange={(event) => setEndNumber(Math.min(selectedChapter.question_count, Math.max(startNumber, Number(event.target.value) || startNumber)))} /></label>
                    </div>
                  ) : (
                    <div className="chapter-range-grid single"><label><span>{text.number}</span><input type="number" min={1} max={selectedChapter.question_count} value={randomCount} onChange={(event) => setRandomCount(Math.min(selectedChapter.question_count, Math.max(1, Number(event.target.value) || 1)))} /></label></div>
                  )}
                  <button type="button" className="chapter-primary-button" onClick={() => void startSession()} disabled={mode === "sequential" && startNumber > endNumber}>{mode === "random" ? <Shuffle size={18} /> : <ListOrdered size={18} />}{text.start}<ChevronRight size={18} /></button>
                </>
              ) : null}
            </div>
          ) : screen === "loading" ? (
            <div className="chapter-state-card"><LoaderCircle className="animate-spin" size={46} /><h3>{text.preparing}</h3></div>
          ) : screen === "error" ? (
            <div className="chapter-state-card error"><XCircle size={46} /><h3>{text.sessionError}</h3><p>{error}</p><button type="button" onClick={resetConfiguration}><RefreshCcw size={16} />{text.retry}</button></div>
          ) : screen === "complete" ? (
            <div className="chapter-state-card complete"><CheckCircle2 size={52} /><h3>{text.result}</h3><div className="chapter-result-score">{correctCount}/{session?.questions.length ?? 0}</div><p>{text.resultText}</p><button type="button" onClick={resetConfiguration}><RefreshCcw size={16} />{text.newSession}</button></div>
          ) : currentQuestion && session ? (
            <div className="chapter-question-card">
              <div className="chapter-question-meta"><span>{text.question} {currentIndex + 1} {text.of} {session.questions.length}</span><strong>#{currentQuestion.question_number}</strong></div>
              <div className="chapter-session-progress"><span style={{ width: `${((currentIndex + 1) / session.questions.length) * 100}%` }} /></div>
              <h3>{currentQuestion.stem}</h3>
              <div className="chapter-choices">
                {choices.map((choice) => {
                  const selected = currentFeedback?.selected_choice === choice.key;
                  const correct = currentFeedback?.correct_choice === choice.key;
                  const className = currentFeedback ? (correct ? "correct" : selected ? "wrong" : "muted") : "";
                  return <button key={choice.key} type="button" className={className} disabled={Boolean(currentFeedback) || submitting} onClick={() => void answerQuestion(choice.key)}><span>{choice.key}</span><strong>{choice.text}</strong>{correct ? <CheckCircle2 size={20} /> : selected && currentFeedback ? <XCircle size={20} /> : null}</button>;
                })}
              </div>
              {currentFeedback ? (
                <div className={`chapter-answer-card ${currentFeedback.is_correct ? "correct" : "wrong"}`}>
                  <div>{currentFeedback.is_correct ? <CheckCircle2 size={22} /> : <XCircle size={22} />}<strong>{currentFeedback.is_correct ? text.correct : text.wrong}</strong></div>
                  <p><span>{text.answer}: {currentFeedback.correct_choice}</span>{currentFeedback.correct_text}</p>
                  <button type="button" onClick={nextQuestion}>{currentIndex + 1 >= session.questions.length ? text.finish : text.next}<ChevronRight size={17} /></button>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
