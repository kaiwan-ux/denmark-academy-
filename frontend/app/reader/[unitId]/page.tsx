"use client";

import { useEffect, useMemo, useState } from "react";
import { BookOpen, Bookmark, CheckCircle2, ChevronLeft, ChevronRight, Download, Highlighter, NotebookPen, Save, Trash2, X } from "lucide-react";
import { completeReadingChapter, deleteRemoteNote, saveLearningState, saveRemoteBookmark, saveRemoteNote } from "@/lib/progress-client";
import { useLanguage } from "@/components/language-provider";

type TrackKey = "pr" | "citizenship";

type Chapter = {
  title: string;
  page: number;
  level?: number;
};

type Book = {
  key: TrackKey;
  label: string;
  title: string;
  subtitle: string;
  file: string;
  totalPages: number;
  chapters: Chapter[];
};

type ReaderNote = {
  id: string;
  track: TrackKey;
  chapter: string;
  page: number;
  quote: string;
  note: string;
  kind: "note" | "highlight";
  createdAt: string;
};

type ReaderProgress = {
  chapterIndex: number;
  pageNumber?: number;
  quote: string;
  note: string;
};

const READER_NOTES_KEY = "denmark-academy-reader-notes";
const READER_LAST_TRACK_KEY = "denmark-academy-reader-last-track";

function readerProgressKey(track: TrackKey) {
  return `denmark-academy-reader-progress-${track}`;
}

function readerDraftKey(track: TrackKey, page: number) {
  return `denmark-academy-reader-draft-${track}-${page}`;
}

function isTrackKey(value: string | null): value is TrackKey {
  return value === "pr" || value === "citizenship";
}

const books: Book[] = [
  {
    key: "pr",
    label: "Permanent Residence",
    title: "Permanent Residence",
    subtitle: "Official learning material",
    file: "/books/permanent-residence-learning-material.pdf",
    totalPages: 155,
    chapters: [
      { title: "Indledning", page: 3 },
      { title: "Fakta-ark 1: Skole", page: 5 },
      { title: "Fakta-ark 2: Uddannelse", page: 11 },
      { title: "Fakta-ark 3: Dagtilbud", page: 17 },
      { title: "Fakta-ark 4: Det danske arbejdsmarked", page: 21 },
      { title: "Fakta-ark 5: Dansk erhvervsliv", page: 30 },
      { title: "Fakta-ark 6: Det danske velfærdssamfund", page: 34 },
      { title: "Fakta-ark 7: Familieliv", page: 40 },
      { title: "Fakta-ark 8: Forenings- og fritidsliv", page: 46 },
      { title: "Fakta-ark 9: Sundhed og sygdom", page: 52 },
      { title: "Fakta-ark 10: Ligestilling", page: 57 },
      { title: "Fakta-ark 11: Demokrati og grundloven", page: 61 },
      { title: "Fakta-ark 12: Det danske retssamfund", page: 67 },
      { title: "Fakta-ark 13: Folketing og regering", page: 71 },
      { title: "Fakta-ark 14: Det lokale selvstyre", page: 76 },
      { title: "Fakta-ark 15: Folkestyret i praksis - valg og partier", page: 81 },
      { title: "Fakta-ark 16: Borgernes rettigheder og pligter", page: 88 },
      { title: "Fakta-ark 17: Religion og kirke", page: 92 },
      { title: "Fakta-ark 18: Danmark og omverdenen", page: 96 },
      { title: "Fakta-ark 19: Danmarks geografi og befolkning", page: 104 },
      { title: "Fakta-ark 20: Danmarks historie før 1945", page: 107 },
      { title: "Fakta-ark 21: Danmarks historie efter 1945", page: 115 },
      { title: "Fakta-ark 22: Dansk kultur", page: 122 },
      { title: "Fakta-ark 23: Traditioner og mærkedage", page: 127 },
      { title: "Fakta-ark 24: Danmarks forsvars- og sikkerhedspolitik", page: 132 },
      { title: "Fakta-ark 25: Diskrimination, antisemitisme, hadforbrydelser og ekstremisme", page: 137 },
      { title: "Fakta-ark 26: Klima", page: 141 },
      { title: "Ordliste", page: 146 }
    ]
  },
  {
    key: "citizenship",
    label: "Citizenship",
    title: "Citizenship Test",
    subtitle: "Official learning material",
    file: "/books/citizenship-learning-material.pdf",
    totalPages: 243,
    chapters: [
      { title: "Kapitel 1 - Danmarks historie", page: 5 },
      { title: "1.1 Indledning", page: 5, level: 1 },
      { title: "1.2 Vikingetid", page: 7, level: 1 },
      { title: "1.3 Middelalder", page: 10, level: 1 },
      { title: "1.4 Reformation, svenskekrige og enevældens indførelse", page: 13, level: 1 },
      { title: "1.5 Søfartsnation og kolonimagt", page: 17, level: 1 },
      { title: "1.6 Oplysningstid og vejen til demokrati", page: 19, level: 1 },
      { title: "1.7 De slesvigske krige", page: 23, level: 1 },
      { title: "1.8 Industrialiseringen og nye politiske bevægelser", page: 26, level: 1 },
      { title: "1.9 Verdenskrig, kriser og socialreformer", page: 32, level: 1 },
      { title: "1.10 Danmark besat af Tyskland", page: 37, level: 1 },
      { title: "1.11 Kold krig, velfærd og ungdomsoprør", page: 42, level: 1 },
      { title: "1.12 Danmark i Europa og oliekrise", page: 49, level: 1 },
      { title: "1.13 Danmark i det globale samfund", page: 54, level: 1 },
      { title: "Kapitel 2 - Det danske demokrati", page: 65 },
      { title: "2.1 Indledning", page: 65, level: 1 },
      { title: "2.2 Den danske styreform", page: 67, level: 1 },
      { title: "2.3 Det danske retssamfund", page: 95, level: 1 },
      { title: "Kapitel 3 - Den danske økonomi", page: 102 },
      { title: "3.1 Indledning", page: 102, level: 1 },
      { title: "3.2 Velfærdssamfundet", page: 104, level: 1 },
      { title: "3.3 Erhvervslivet", page: 113, level: 1 },
      { title: "3.4 Arbejdsmarkedet", page: 116, level: 1 },
      { title: "Kapitel 4 - Danmark og omverdenen", page: 120 },
      { title: "4.1 Indledning", page: 120, level: 1 },
      { title: "4.2 Danmark i Europa", page: 121, level: 1 },
      { title: "4.3 Danmarks globale samarbejde", page: 130, level: 1 },
      { title: "4.4 Danmarks forsvars- og sikkerhedspolitik", page: 135, level: 1 },
      { title: "Kapitel 5 - Dansk kulturliv", page: 143 },
      { title: "5.1 Indledning", page: 143, level: 1 },
      { title: "5.2 Litteratur", page: 145, level: 1 },
      { title: "5.3 Billedkunst og skulptur", page: 152, level: 1 },
      { title: "5.4 Musik", page: 157, level: 1 },
      { title: "5.5 Arkitektur og design", page: 160, level: 1 },
      { title: "5.6 Scenekunst", page: 163, level: 1 },
      { title: "5.7 Film", page: 167, level: 1 },
      { title: "Kapitel 6 - Temaopslag", page: 173 },
      { title: "6.1 Danmarks geografi", page: 173, level: 1 },
      { title: "6.2 Danmarks seværdigheder", page: 176, level: 1 },
      { title: "6.3 Det danske flag", page: 189, level: 1 },
      { title: "6.4 Kongehuset", page: 190, level: 1 },
      { title: "6.5 Indvandring til Danmark gennem tiderne", page: 192, level: 1 },
      { title: "6.6 Rigsfællesskabet mellem Danmark, Grønland og Færøerne", page: 195, level: 1 },
      { title: "6.7 Danmark og Norden", page: 205, level: 1 },
      { title: "6.8 Dansk videnskab og tænkning", page: 208, level: 1 },
      { title: "6.9 Kirke og religion i Danmark", page: 212, level: 1 },
      { title: "6.10 Skikke og mærkedage", page: 215, level: 1 },
      { title: "6.11 N.F.S. Grundtvig, danskhed, højskoler og kirkeliv", page: 218, level: 1 },
      { title: "6.12 Skolegang og uddannelse i Danmark", page: 221, level: 1 },
      { title: "6.13 Familie og familieliv", page: 226, level: 1 },
      { title: "6.14 Diskrimination, antisemitisme, hadforbrydelser og ekstremisme", page: 228, level: 1 },
      { title: "6.15 Ligestilling mellem kønnene", page: 231, level: 1 },
      { title: "6.16 Sundhed og sundhedsvæsen", page: 235, level: 1 },
      { title: "6.17 Klima", page: 239, level: 1 }
    ]
  }
];

export default function ReaderPage() {
  const { t, language } = useLanguage();
  const [track, setTrack] = useState<TrackKey>("citizenship");
  const [chapterIndex, setChapterIndex] = useState(0);
  const [quote, setQuote] = useState("");
  const [note, setNote] = useState("");
  const [notes, setNotes] = useState<ReaderNote[]>([]);
  const [storageReady, setStorageReady] = useState(false);
  const [completedChapterKeys, setCompletedChapterKeys] = useState<Set<string>>(new Set());
  const [completionPending, setCompletionPending] = useState(false);
  const [pdfLoaded, setPdfLoaded] = useState(false);
  const [pageNumber, setPageNumber] = useState(5);

  const book = useMemo(() => books.find((item) => item.key === track) ?? books[0], [track]);
  const chapter = book.chapters[chapterIndex] ?? book.chapters[0];
  const pdfSource = `${book.file}#page=${pageNumber}&zoom=page-width&toolbar=0&navpanes=0&scrollbar=1&view=FitH`;
  const visibleNotes = notes.filter((item) => item.track === book.key);

  useEffect(() => {
    setPdfLoaded(false);
  }, [pdfSource]);


  useEffect(() => {
    const controller = new AbortController();
    void fetch(book.file, {
      headers: { Range: "bytes=0-131071" },
      cache: "force-cache",
      signal: controller.signal,
    }).catch(() => undefined);
    return () => controller.abort();
  }, [book.file]);

  useEffect(() => {
    const savedNotes = window.localStorage.getItem(READER_NOTES_KEY);
    if (savedNotes) {
      const restoredNotes = JSON.parse(savedNotes) as ReaderNote[];
      setNotes(restoredNotes);
      restoredNotes.forEach((item) => {
        void saveRemoteNote({ module: "reading_material", entity_id: item.id, body: item.note || item.quote, route: "/reader/demo", anchor: { track: item.track, chapter: item.chapter, page: item.page, quote: item.quote, kind: item.kind } });
      });
    }

    const requestedTrack = new URLSearchParams(window.location.search).get("track");
    const savedTrack = window.localStorage.getItem(READER_LAST_TRACK_KEY);
    const nextTrack = isTrackKey(requestedTrack) ? requestedTrack : isTrackKey(savedTrack) ? savedTrack : "citizenship";
    const progress = loadProgress(nextTrack);
    const nextBook = books.find((item) => item.key === nextTrack) ?? books[0];

    setTrack(nextTrack);
    const nextIndex = clampChapterIndex(progress?.chapterIndex ?? 0, nextBook);
    const draft = loadDraft(nextTrack, nextBook.chapters[nextIndex]?.page ?? 1);
    setChapterIndex(nextIndex);
    setPageNumber(progress?.pageNumber ?? nextBook.chapters[nextIndex]?.page ?? 1);
    setQuote(draft?.quote ?? progress?.quote ?? "");
    setNote(draft?.note ?? progress?.note ?? "");
    setStorageReady(true);
    fetch("/api/account/progress/chapters", { cache: "no-store" })
      .then((response) => response.ok ? response.json() : [])
      .then((items) => setCompletedChapterKeys(new Set(items.map((item: { track: string; chapter_key: string }) => item.track + ":" + item.chapter_key))))
      .catch(() => undefined);

    fetch("/api/account/progress/states/reading_material?state_key=" + nextTrack, { cache: "no-store" })
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => {
        const saved = payload?.state?.state;
        if (!saved) return;
        const remoteTrack = isTrackKey(saved.track) ? saved.track : nextTrack;
        const remoteBook = books.find((item) => item.key === remoteTrack) ?? books[0];
        const remoteIndex = clampChapterIndex(Number(saved.chapter_index ?? 0), remoteBook);
        setTrack(remoteTrack);
        setChapterIndex(remoteIndex);
        setPageNumber(Math.min(remoteBook.totalPages, Math.max(1, Number(saved.page ?? remoteBook.chapters[remoteIndex]?.page ?? 1))));
        setQuote(saved.quote ?? "");
        setNote(saved.note ?? "");
      }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!storageReady) return;
    window.localStorage.setItem(READER_NOTES_KEY, JSON.stringify(notes));
  }, [notes, storageReady]);

  useEffect(() => {
    if (!storageReady) return;
    window.localStorage.setItem(READER_LAST_TRACK_KEY, track);
    window.localStorage.setItem(readerProgressKey(track), JSON.stringify({ chapterIndex, pageNumber, quote, note } satisfies ReaderProgress));
    window.localStorage.setItem(readerDraftKey(track, chapter.page), JSON.stringify({ quote, note }));
    const timer = window.setTimeout(() => {
      void saveLearningState("reading_material", {
        state_key: track, route: "/reader/demo?track=" + track, entity_id: track + ":" + chapter.page,
        title: book.label + " reading", completion_percent: book.chapters.length ? ([...completedChapterKeys].filter((key) => key.startsWith(track + ":")).length / book.chapters.length) * 100 : 0,
        state: { track, chapter_index: chapterIndex, page: pageNumber, quote, note, completed_items: [...completedChapterKeys].filter((key) => key.startsWith(track + ":")).length, total_items: book.chapters.length }
      });
    }, 600);
    return () => window.clearTimeout(timer);
  }, [track, chapterIndex, pageNumber, quote, note, storageReady, chapter.page, chapter.title, book.chapters.length, completedChapterKeys]);

  function loadProgress(nextTrack: TrackKey): ReaderProgress | null {
    const saved = window.localStorage.getItem(readerProgressKey(nextTrack));
    if (!saved) return null;
    try {
      return JSON.parse(saved) as ReaderProgress;
    } catch {
      return null;
    }
  }

  function clampChapterIndex(value: number, nextBook: Book) {
    if (!Number.isFinite(value)) return 0;
    return Math.min(Math.max(0, value), nextBook.chapters.length - 1);
  }

  function selectBook(nextTrack: TrackKey) {
    const progress = loadProgress(nextTrack);
    const nextBook = books.find((item) => item.key === nextTrack) ?? books[0];
    setTrack(nextTrack);
    const nextIndex = clampChapterIndex(progress?.chapterIndex ?? 0, nextBook);
    const draft = loadDraft(nextTrack, nextBook.chapters[nextIndex]?.page ?? 1);
    setChapterIndex(nextIndex);
    setPageNumber(progress?.pageNumber ?? nextBook.chapters[nextIndex]?.page ?? 1);
    setQuote(draft?.quote ?? progress?.quote ?? "");
    setNote(draft?.note ?? progress?.note ?? "");
  }

  function loadDraft(nextTrack: TrackKey, page: number): Pick<ReaderProgress, "quote" | "note"> | null {
    const saved = window.localStorage.getItem(readerDraftKey(nextTrack, page));
    if (!saved) return null;
    try {
      return JSON.parse(saved) as Pick<ReaderProgress, "quote" | "note">;
    } catch {
      return null;
    }
  }

  function selectChapter(index: number) {
    const nextChapter = book.chapters[index];
    const draft = loadDraft(book.key, nextChapter?.page ?? 1);
    setChapterIndex(index);
    setPageNumber(nextChapter?.page ?? 1);
    setQuote(draft?.quote ?? "");
    setNote(draft?.note ?? "");
  }

  function goToPage(nextPage: number) {
    if (!Number.isFinite(nextPage)) return;
    setPageNumber(Math.min(book.totalPages, Math.max(1, Math.round(nextPage))));
  }


  async function markChapterComplete() {
    const chapterKey = chapter.page + ":" + chapter.title;
    const fullKey = track + ":" + chapterKey;
    if (completedChapterKeys.has(fullKey) || completionPending) return;
    setCompletionPending(true);
    try {
      const response = await completeReadingChapter({
        track,
        chapter_key: chapterKey,
        chapter_title: chapter.title,
        page_number: chapter.page,
        total_chapters: book.chapters.length,
        route: "/reader/demo?track=" + track,
      });
      if (!response || !response.ok) throw new Error("Could not complete chapter");
      const next = new Set(completedChapterKeys);
      next.add(fullKey);
      setCompletedChapterKeys(next);
      const result = await response.json();
      void saveLearningState("reading_material", {
        state_key: track,
        route: "/reader/demo?track=" + track,
        entity_id: fullKey,
        title: book.label + " reading",
        completion_percent: result.completion_percent,
        completed: result.completed_items >= result.total_items,
        state: { track, chapter_index: chapterIndex, page: chapter.page, completed_items: result.completed_items, total_items: result.total_items }
      });
    } finally {
      setCompletionPending(false);
    }
  }
  function discardDraft() {
    setQuote("");
    setNote("");
  }

  function saveItem(kind: ReaderNote["kind"]) {
    if (!quote.trim() && !note.trim()) return;
    const itemId = crypto.randomUUID();
    setNotes((current) => [
      {
        id: itemId,
        track: book.key,
        chapter: chapter.title,
        page: chapter.page,
        quote: quote.trim(),
        note: note.trim(),
        kind,
        createdAt: new Date().toISOString()
      },
      ...current
    ]);
    void saveRemoteNote({ module: "reading_material", entity_id: itemId, body: note.trim() || quote.trim(), route: "/reader/demo?track=" + track, anchor: { track: book.key, chapter: chapter.title, page: chapter.page, quote: quote.trim(), kind } });
    if (kind === "highlight") {
      void saveRemoteBookmark({ module: "reading_material", entity_id: book.key + ":" + chapter.page + ":" + quote.trim().slice(0, 80), title: chapter.title, route: "/reader/demo?track=" + track, metadata: { page: chapter.page, quote: quote.trim() } });
    }
    discardDraft();
  }

  function deleteNote(id: string) {
    setNotes((current) => current.filter((item) => item.id !== id));
    void deleteRemoteNote("reading_material", id);
  }

  function downloadNotes() {
    const lines = visibleNotes.length
      ? visibleNotes.map((item, index) => [
          `${index + 1}. ${item.kind.toUpperCase()} - ${item.chapter} (page ${item.page})`,
          item.quote ? `Selected text: ${item.quote}` : "",
          item.note ? `Note: ${item.note}` : "",
          `Saved: ${new Date(item.createdAt).toLocaleString()}`
        ].filter(Boolean).join("\n"))
      : ["No notes saved for this book."];
    const blob = new Blob([`${book.label} notes\n\n${lines.join("\n\n")}`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${book.key}-reader-notes.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="reader-page space-y-8 pb-6">
      <section className="motion-panel mx-auto max-w-5xl text-center">
        <div className="text-xs font-semibold uppercase tracking-[0.3em] text-brass/75">Reading room</div>
        <h1 className="aesthetic-serif-strong mt-3 text-5xl leading-tight sm:text-6xl">{t("Open the official book.")}</h1>
        <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-[#c8ad88]">{t("Select an exam book, choose a chapter, and keep your private notes beside the page. The official PDF remains unchanged.")}</p>
      </section>

      <section className="motion-panel rounded-[18px] border border-[#6f4324]/60 bg-[radial-gradient(circle_at_50%_0%,rgba(214,168,79,0.18),transparent_28rem),linear-gradient(135deg,#2a150b,#120805)] p-3 shadow-[0_34px_150px_rgba(0,0,0,0.5)] sm:p-5">
        <div className="rounded-[14px] border border-black/40 bg-[#2a160c] p-2 shadow-[inset_0_0_0_1px_rgba(255,226,168,0.08)]">
          <div className="reader-workspace grid overflow-hidden rounded-[11px] bg-[#3a2112] shadow-[inset_0_0_38px_rgba(0,0,0,0.5)]">
            <aside className="reader-chapters-panel relative min-h-[760px] bg-[#d9bf91] p-6 text-[#2b180c] shadow-[inset_-28px_0_44px_rgba(74,39,18,0.2)]">
              <div className="absolute right-0 top-0 h-full w-6 bg-gradient-to-r from-transparent to-[#70421f]/30" />
              <div className="relative z-10">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]"><BookOpen size={15} aria-hidden />Choose book</div>
                <div className="mt-5 grid gap-3">
                  {books.map((item) => (
                    <button key={item.key} type="button" onClick={() => selectBook(item.key)} className={`rounded-[8px] border px-4 py-4 text-left transition ${item.key === book.key ? "border-[#5e331a] bg-[#5e331a] text-[#f7ead4] shadow-[0_14px_34px_rgba(80,39,16,0.28)]" : "border-[#946333]/50 bg-[#ead6b2]/70 text-[#4b2a14] hover:border-[#5e331a]"}`}>
                      <span className="block text-sm font-bold">{t(item.label)}</span>
                      <span className="mt-1 block text-xs opacity-75">{item.chapters.length} {language === "da" ? "kapitler" : "chapters"}</span>
                    </button>
                  ))}
                </div>

                <div className="mt-8 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]"><Bookmark size={15} aria-hidden />{t("Chapters")}</div>
                <div className="mt-4 max-h-[470px] space-y-1 overflow-y-auto pr-1">
                  {book.chapters.map((item, index) => (
                    <button key={`${item.title}-${item.page}`} type="button" onClick={() => selectChapter(index)} className={`group grid w-full items-center gap-3 rounded-[8px] px-3 py-2.5 text-left transition ${item.level ? "grid-cols-[22px_1fr] pl-7" : "grid-cols-[34px_1fr]"} ${index === chapterIndex ? "bg-[#a86d36] text-[#2b180c]" : "hover:bg-[#d8bd93]/55"}`}>
                      <span className={`${item.level ? "h-5 w-5 text-[10px]" : "h-8 w-8 text-xs"} flex items-center justify-center rounded-full border border-[#70421f]/35 font-bold`}>{String(index + 1).padStart(2, "0")}</span>
                      <span>
                        <span className={`${item.level ? "text-xs" : "text-sm"} block font-bold`}>{item.title}</span>
                        <span className="block text-xs text-[#7b5636]">{language === "da" ? "Side" : "Page"} {item.page}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </aside>

            <main className="reader-book-panel relative min-h-[760px] bg-[#ead6b2] p-4 text-[#2b180c] shadow-[inset_28px_0_44px_rgba(74,39,18,0.18),inset_-28px_0_44px_rgba(74,39,18,0.12)] sm:p-6">
              <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-[#70421f]/18 to-transparent" />
              <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-[#70421f]/14 to-transparent" />
              <div className="relative z-10 flex min-h-full flex-col">
                <div className="mb-4 flex flex-wrap items-end justify-between gap-3 border-b border-[#9b7149]/25 pb-4">
                  <div>
                    <div className="text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]">{book.label}</div>
                    <h2 className="mt-1 text-3xl font-bold tracking-tight text-[#3a210f]">{book.title}</h2>
                  </div>
                  <button type="button" onClick={markChapterComplete} disabled={completionPending || completedChapterKeys.has(track + ":" + chapter.page + ":" + chapter.title)} className="reader-complete-button">
                    <CheckCircle2 size={17} aria-hidden />
                    {completedChapterKeys.has(track + ":" + chapter.page + ":" + chapter.title) ? "Chapter completed" : completionPending ? "Saving..." : "Mark chapter complete"}
                  </button>
                </div>
                <div className="reader-toolbar" role="toolbar" aria-label={t("Reading controls")}>
                  <div className="reader-toolbar-group">
                    <button type="button" onClick={() => goToPage(pageNumber - 1)} disabled={pageNumber <= 1} title={t("Previous page")} aria-label={t("Previous page")}><ChevronLeft size={18} aria-hidden /><span>{t("Previous page")}</span></button>
                    <span className="reader-page-indicator">{t("Page")} {pageNumber} / {book.totalPages}</span>
                    <button type="button" onClick={() => goToPage(pageNumber + 1)} disabled={pageNumber >= book.totalPages} title={t("Next page")} aria-label={t("Next page")}><span>{t("Next page")}</span><ChevronRight size={18} aria-hidden /></button>
                  </div>
                </div>
                <div className="reader-pdf-frame grow overflow-hidden rounded-[8px] border border-[#70421f]/30 bg-white shadow-[0_18px_54px_rgba(80,39,18,0.22)]" aria-busy={!pdfLoaded}>
                  {!pdfLoaded ? (
                    <div className="reader-pdf-skeleton" role="status" aria-live="polite">
                      <span className="reader-pdf-skeleton-title">Loading official book…</span>
                      <span className="reader-pdf-skeleton-line" />
                      <span className="reader-pdf-skeleton-line is-short" />
                      <span className="reader-pdf-skeleton-line" />
                    </div>
                  ) : null}
                  <iframe
                    key={`${book.key}-${pageNumber}`}
                    title={book.title}
                    src={pdfSource}
                    className={`h-[650px] w-full bg-white ${pdfLoaded ? "is-loaded" : "is-loading"}`}
                    loading="eager"
                    onLoad={() => setPdfLoaded(true)}
                  />
                </div>
              </div>
            </main>

            <aside className="reader-notes-panel relative min-h-[760px] bg-[#d0ae78] p-5 text-[#2b180c] shadow-[inset_28px_0_44px_rgba(74,39,18,0.2)]">
              <div className="absolute left-0 top-0 h-full w-6 bg-gradient-to-l from-transparent to-[#70421f]/26" />
              <div className="relative z-10">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.24em] text-[#70421f]"><NotebookPen size={15} aria-hidden />Study margin</div>
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={downloadNotes} className="inline-flex h-8 items-center gap-1 rounded-[7px] border border-[#70421f]/35 bg-[#f7ead4]/50 px-2 text-xs font-bold text-[#4b2a14]"><Download size={13} aria-hidden />{t("Download")}</button>
                  </div>
                </div>
                <p className="mt-3 text-sm leading-6 text-[#654223]">Private notes and highlights remain saved when you change page or book.</p>

                <label className="mt-6 block text-xs font-bold uppercase tracking-[0.16em] text-[#70421f]">Selected text</label>
                <textarea value={quote} onChange={(event) => setQuote(event.target.value)} placeholder="Paste a line from the page..." className="mt-2 min-h-24 w-full rounded-[8px] border border-[#946333]/55 bg-[#efe0bf]/75 p-3 text-sm leading-6 text-[#2b180c] outline-none placeholder:text-[#8c6a48] focus:border-[#5e331a]" />

                <label className="mt-4 block text-xs font-bold uppercase tracking-[0.16em] text-[#70421f]">Your note</label>
                <textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Write your thought..." className="mt-2 min-h-28 w-full rounded-[8px] border border-[#946333]/55 bg-[#efe0bf]/75 p-3 text-sm leading-6 text-[#2b180c] outline-none placeholder:text-[#8c6a48] focus:border-[#5e331a]" />

                <div className="mt-4 grid grid-cols-3 gap-2">
                  <button type="button" onClick={() => saveItem("highlight")} className="inline-flex h-10 items-center justify-center gap-2 rounded-[8px] bg-[#72401f] text-sm font-bold text-[#f7ead4]"><Highlighter size={15} aria-hidden />Mark</button>
                  <button type="button" onClick={() => saveItem("note")} className="inline-flex h-10 items-center justify-center gap-2 rounded-[8px] border border-[#70421f]/45 bg-[#efe0bf]/65 text-sm font-bold text-[#4b2a14]"><Save size={15} aria-hidden />Save</button>
                  <button type="button" onClick={discardDraft} className="inline-flex h-10 items-center justify-center gap-2 rounded-[8px] border border-[#70421f]/35 bg-transparent text-sm font-bold text-[#4b2a14]"><X size={15} aria-hidden />Clear</button>
                </div>

                <div className="mt-6 max-h-72 space-y-3 overflow-y-auto pr-1">
                  {visibleNotes.length === 0 ? (
                    <div className="rounded-[8px] border border-[#946333]/45 bg-[#efe0bf]/60 p-3 text-sm leading-6 text-[#654223]">No notes yet.</div>
                  ) : visibleNotes.map((item) => (
                    <article key={item.id} className="rounded-[8px] border border-[#946333]/45 bg-[#efe0bf]/60 p-3 shadow-[0_10px_28px_rgba(80,39,16,0.12)]">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#70421f]">{item.kind} - page {item.page}</div>
                          <div className="mt-1 text-sm font-bold text-[#3a210f]">{item.chapter}</div>
                        </div>
                        <button type="button" onClick={() => deleteNote(item.id)} className="rounded-[6px] p-1 text-[#70421f] hover:bg-[#70421f]/10" aria-label="Delete note"><Trash2 size={14} aria-hidden /></button>
                      </div>
                      {item.quote ? <p className="mt-2 border-l-2 border-[#70421f]/50 pl-3 text-sm leading-6 text-[#654223]">{item.quote}</p> : null}
                      {item.note ? <p className="mt-2 text-sm leading-6 text-[#4b2a14]">{item.note}</p> : null}
                    </article>
                  ))}
                </div>
              </div>
            </aside>
          </div>
        </div>
      </section>
    </div>
  );
}






