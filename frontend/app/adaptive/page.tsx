import { BarChart3, CalendarClock, Compass, Gauge, RotateCcw, TimerReset } from "lucide-react";
import { CommandButton, InsightList, PageHeader, RitualList, SignalBadge, StudioSteps, StudyInstrument, Surface } from "@/components/ui";

export default function AdaptivePage() {
  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Personal path" title="The academy learns how you study." description="Reading pace, practice accuracy, confidence, revision habits, and mock results shape a study path that feels personal instead of generic." action={<CommandButton href="/revision">Review due items</CommandButton>} />
      <StudyInstrument items={[
        { label: "Consistency", value: "6 days", detail: "Study rhythm held this week." },
        { label: "Learning pace", value: "+14%", detail: "Concepts are stabilizing faster than last week." },
        { label: "Risk areas", value: "3", detail: "Topics need attention before a full mock." }
      ]} />
      <section className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <Surface className="p-5">
          <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[#fff1d2]">Adaptive cycle</h2><SignalBadge label="Live" /></div>
          <StudioSteps steps={[
            { icon: Gauge, title: "Read the signal", detail: "Accuracy, time, confidence, and revision outcomes are combined.", state: "Sense" },
            { icon: Compass, title: "Choose next work", detail: "The next task targets the concept with the highest learning value.", state: "Aim" },
            { icon: RotateCcw, title: "Schedule review", detail: "Weak or low-confidence answers return at the right moment.", state: "Repeat" },
            { icon: TimerReset, title: "Raise pressure", detail: "Difficulty increases only when the foundation is ready.", state: "Grow" }
          ]} />
        </Surface>
        <Surface className="p-5">
          <h2 className="text-lg font-semibold text-[#fff1d2]">This week</h2>
          <RitualList items={[
            { time: "Mon", title: "Foundation repair", detail: "Two short reading sections and one review set." },
            { time: "Wed", title: "Mixed practice", detail: "A balanced set across your weakest ideas." },
            { time: "Fri", title: "Exam rehearsal", detail: "A timed block once the review shelf is clear." }
          ]} />
        </Surface>
      </section>
      <Surface className="p-5"><InsightList items={["The path updates after meaningful study actions, not random page visits.", "Students can see why a task was selected.", "Difficulty changes gradually so progress feels challenging but fair."]} /></Surface>
    </div>
  );
}
