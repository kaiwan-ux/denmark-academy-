import { BookOpen, BrainCircuit, Compass, MessageSquareText, Search, Sparkles } from "lucide-react";
import { CommandButton, GhostButton, InsightList, PageHeader, RitualList, SignalBadge, StudioSteps, Surface } from "@/components/ui";

export default function MentorPage() {
  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Mentor desk" title="A quiet teacher for the exact point where you are stuck." description="The mentor uses your study history and trusted learning sources to explain, redirect, and choose the next useful action." action={<CommandButton href="/practice">Take next step</CommandButton>} />
      <section className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <Surface className="p-5">
          <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[#fff1d2]">Ask with context</h2><SignalBadge label="Source-aware" /></div>
          <div className="rounded-[10px] border border-brass/20 bg-[#100703] p-4">
            <div className="text-sm text-[#c8ad88]">Student question</div>
            <p className="mt-2 text-xl leading-8 text-[#fff1d2]">Why is this citizenship question about parliament wrong when I chose the closest answer?</p>
          </div>
          <div className="mt-4 rounded-[10px] border border-brass/20 bg-white/[0.035] p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-brass"><MessageSquareText size={16} aria-hidden />Mentor response</div>
            <p className="mt-2 leading-7 text-[#d6bf98]">First, compare the wording with the official answer. The mistake is not the topic, but the role: the question asks who forms government after an election, not who passes a law.</p>
          </div>
        </Surface>
        <Surface className="p-5">
          <h2 className="text-lg font-semibold text-[#fff1d2]">Mentor behavior</h2>
          <StudioSteps steps={[
            { icon: Search, title: "Find supporting material", detail: "The answer stays connected to trusted study sources.", state: "Ground" },
            { icon: BrainCircuit, title: "Match the student", detail: "Tone and difficulty adapt to mastery and confidence.", state: "Adjust" },
            { icon: Compass, title: "Give the next move", detail: "The response ends with a useful study action.", state: "Guide" },
            { icon: Sparkles, title: "Create only when useful", detail: "Notes, flashcards, and drafts are made for learning, not noise.", state: "Focus" }
          ]} />
        </Surface>
      </section>
      <Surface className="p-5"><RitualList items={[{ time: "Now", title: "Review the missed concept", detail: "Read the short explanation and answer one similar question." }, { time: "Next", title: "Return to the chapter", detail: "Revisit the source section that supports the answer." }, { time: "Later", title: "Try a timed block", detail: "Only after the weak idea is stable." }]} /></Surface>
    </div>
  );
}
