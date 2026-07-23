"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, BookOpen, CheckCircle2, Clock3, Flame, NotebookPen, Target, TrendingUp, XCircle, type LucideIcon } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { useLanguage } from "@/components/language-provider";

type ModuleMetric = {
  module: string; state_key: string; title?: string | null; route: string;
  attempted: number; completed_items: number; total_items: number;
  correct: number; incorrect: number; accuracy: number; completion: number;
};
type Summary = {
  totals: { attempted:number; correct:number; incorrect:number; accuracy:number; study_streak:number; study_time_seconds:number; completed_chapters:number; overall_completion:number; notes:number; completed_mock_exams:number };
  modules: ModuleMetric[];
};
type ContinueItem = {
  id:string; route:string; title?:string; module:string; state_key:string;
  completion_percent:number; state?:{ completed_items?:number; total_items?:number; [key:string]:unknown };
};

const labels: Record<string,string> = {
  reading_material:"Reading Material", knowledge_mcqs:"Knowledge Base MCQs",
  ai_generated_mcqs:"AI Generated MCQs", chapter_practice:"Chapter Practice MCQs", past_papers:"Past Papers",
  current_affairs:"Current Affairs", danish_values:"Danish Values",
  practice_questions:"Practice Questions", mock_exam:"Mock Exams"
};
const trackLabel = (key:string) => key === "citizenship" ? "Citizenship" : key === "pr" ? "Permanent Residence" : "";
const formatTime = (seconds:number) => seconds < 60 ? `${seconds}s` : seconds < 3600 ? `${Math.floor(seconds/60)}m ${seconds%60}s` : `${Math.floor(seconds/3600)}h ${Math.floor((seconds%3600)/60)}m`;

export default function ProgressPage() {
  const { user } = useAuth();
  const { t, language } = useLanguage();
  const [summary,setSummary] = useState<Summary|null>(null);
  const [resumeItems,setResumeItems] = useState<ContinueItem[]>([]);
  const [error,setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [summaryResponse,continueResponse] = await Promise.all([
        fetch("/api/account/progress/summary",{cache:"no-store"}),
        fetch("/api/account/progress/continue",{cache:"no-store"})
      ]);
      if (!summaryResponse.ok) throw new Error("Could not load your analytics.");
      setSummary(await summaryResponse.json());
      const next = await continueResponse.json();
      setResumeItems(next.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load your analytics.");
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 30000);
    return () => window.clearInterval(interval);
  }, [load]);

  function localizeProgressTitle(value: string) {
    if (language !== "da") return value;
    const exact: Record<string, string> = {
      "Citizenship reading": "Læsning – indfødsret",
      "Permanent Residence reading": "Læsning – permanent ophold",
      "Citizenship chapter practice": "Kapiteltræning – indfødsret",
      "Permanent Residence chapter practice": "Kapiteltræning – permanent ophold",
      "Citizenship past papers": "Tidligere prøver – indfødsret",
      "Permanent Residence past papers": "Tidligere prøver – permanent ophold",
      "Current Affairs": "Aktuelle emner"
    };
    return exact[value] ?? t(value);
  }

  function moduleSummary(item: ModuleMetric) {
    const total = item.total_items ? (language === "da" ? " af " + item.total_items : " of " + item.total_items) : "";
    return language === "da"
      ? item.completed_items + total + " gennemført · " + item.attempted + " forsøgt · " + item.accuracy + "% nøjagtighed"
      : item.completed_items + total + " completed · " + item.attempted + " attempted · " + item.accuracy + "% accuracy";
  }
  const circumference=2*Math.PI*46;
  const accuracy=summary?.totals.accuracy||0;
  const visibleModules=useMemo(() => summary?.modules.filter(item => item.attempted > 0 || item.completed_items > 0 || item.total_items > 0) || [], [summary]);
  const resumable=useMemo(() => resumeItems.filter(item => {
    const completed=Number(item.state?.completed_items ?? 0);
    const total=Number(item.state?.total_items ?? 0);
    return total > 0 && completed < total;
  }), [resumeItems]);
  const metricCards: {label:string;value:string|number;Icon:LucideIcon}[] = [
    {label:"Questions attempted",value:summary?.totals.attempted||0,Icon:Target},
    {label:"Correct answers",value:summary?.totals.correct||0,Icon:CheckCircle2},
    {label:"Incorrect answers",value:summary?.totals.incorrect||0,Icon:XCircle},
    {label:"Study streak",value:(summary?.totals.study_streak||0)+(language === "da" ? " dage" : " days"),Icon:Flame},
    {label:"Study time",value:formatTime(summary?.totals.study_time_seconds||0),Icon:Clock3},
    {label:"Completed chapters",value:summary?.totals.completed_chapters||0,Icon:BookOpen},
    {label:"Notes",value:summary?.totals.notes||0,Icon:NotebookPen},
  ];

  if(error) return <div className="progress-empty">{error}</div>;
  return <div className="progress-page">
    <section className="progress-hero">
      <div><span className="progress-kicker">MY PROGRESS / LIVE STUDY RECORD</span><h1>{user?.display_name ? (language === "da" ? user.display_name.split(" ")[0] + "s forberedelse," : user.display_name.split(" ")[0] + "\u2019s preparation,") : t("Your preparation,")}<br/><em>made visible.</em></h1><p>Every answer, completed chapter and study minute contributes to this permanent learning record.</p></div>
      <div className="accuracy-ring"><svg viewBox="0 0 108 108"><circle cx="54" cy="54" r="46"/><circle className="ring-value" cx="54" cy="54" r="46" style={{strokeDasharray:circumference,strokeDashoffset:circumference-(accuracy/100)*circumference}}/></svg><strong>{summary?`${accuracy}%`:"—"}</strong><span>OVERALL ACCURACY</span></div>
    </section>

    {resumable.length ? <section className="resume-section">
      <div className="panel-title"><div><span>CONTINUE EACH LEARNING PATH</span><h2>Resume exactly where you stopped</h2></div><BookOpen size={26}/></div>
      <div className="resume-grid">{resumable.map(item => {
        const completed=Number(item.state?.completed_items ?? 0);
        const total=Number(item.state?.total_items ?? 0);
        return <article className="resume-card" key={item.id}>
          <div><span>{t(labels[item.module]||item.module)}</span><h3>{localizeProgressTitle(item.title || [t(trackLabel(item.state_key)),t(labels[item.module])].filter(Boolean).join(" "))}</h3><p><strong>{completed}</strong> {language === "da" ? "af" : "of"} <strong>{total}</strong> {language === "da" ? "gennemført · Næste emne" : "completed · Next item"} {Math.min(completed+1,total)}</p></div>
          <div className="resume-progress"><i style={{width:`${total ? completed/total*100 : 0}%`}}/></div>
          <Link href={item.route}>{language === "da" ? "Fortsæt fra" : "Resume from"} {Math.min(completed+1,total)} <ArrowRight size={17}/></Link>
        </article>;
      })}</div>
    </section> : null}

    <section className="metric-grid">{metricCards.map(({label,value,Icon})=><article className="metric-card" key={label}><Icon size={20}/><span>{label}</span><strong>{value}</strong></article>)}</section>

    <section className="analytics-panel module-panel full-width">
      <div className="panel-title"><div><span>MODULE ANALYTICS</span><h2>Progress by active learning path</h2></div><TrendingUp size={26}/></div>
      {visibleModules.length ? <div className="module-list">{visibleModules.map(item => {
        const title=localizeProgressTitle(item.title || [t(trackLabel(item.state_key)),t(labels[item.module]||item.module)].filter(Boolean).join(" "));
        return <div className="module-row" key={item.module+":"+item.state_key}>
          <div><strong>{title}</strong><span>{moduleSummary(item)}</span></div>
          <div className="module-progress"><i style={{width:`${item.completion}%`}}/><span>{Math.round(item.completion)}%</span></div>
        </div>;
      })}</div> : <p className="empty-insight">Your module analytics will appear after you begin a learning path.</p>}
    </section>
  </div>;
}

