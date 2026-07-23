import { BookMarked, GitBranch, GraduationCap, HelpCircle, Library, Route } from "lucide-react";
import { CommandButton, InsightList, PageHeader, SignalBadge, StudioSteps, Surface } from "@/components/ui";

export default function GraphPage() {
  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Learning map" title="See how books, concepts, questions, and revision connect." description="The map helps the mentor understand which missing idea causes later mistakes and which path gets a student ready fastest." action={<CommandButton href="/adaptive">Open personal path</CommandButton>} />
      <section className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <Surface className="relative min-h-[420px] overflow-hidden p-5">
          <div className="absolute inset-0 wood-ring opacity-50" />
          <div className="relative z-10 flex h-full min-h-[380px] items-center justify-center">
            <div className="grid w-full max-w-3xl gap-5 text-center sm:grid-cols-3">
              {["Books", "Concepts", "Questions", "Attempts", "Weak spots", "Revision"].map((node, index) => (
                <div key={node} className="motion-map rounded-[10px] border border-brass/25 bg-[#211009]/85 p-5 shadow-[0_18px_60px_rgba(0,0,0,0.28)]" style={{ transform: `translateY(${index % 2 ? 26 : 0}px)` }}>
                  <div className="text-sm font-semibold uppercase tracking-[0.16em] text-brass/75">{index < 3 ? "Knowledge" : "Student"}</div>
                  <div className="mt-2 text-xl font-semibold text-[#fff1d2]">{node}</div>
                </div>
              ))}
            </div>
          </div>
        </Surface>
        <Surface className="p-5">
          <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[#fff1d2]">Questions the map can answer</h2><SignalBadge label="Connected" /></div>
          <InsightList items={["Which concept causes the most later mistakes?", "Which prerequisite should be mastered before the next chapter?", "What is the shortest route from current ability to exam readiness?", "Which revision item should return first?" ]} />
        </Surface>
      </section>
      <Surface className="p-5">
        <StudioSteps steps={[
          { icon: Library, title: "Course and chapter", detail: "The broad learning shelf." },
          { icon: BookMarked, title: "Topic and concept", detail: "The exact ideas a student must master." },
          { icon: HelpCircle, title: "Question and answer", detail: "Where understanding is tested." },
          { icon: GraduationCap, title: "Student attempt", detail: "Where weakness and progress become visible." },
          { icon: Route, title: "Next learning path", detail: "The recommended route forward." },
          { icon: GitBranch, title: "Prerequisite chain", detail: "The ideas that support later chapters." }
        ]} />
      </Surface>
    </div>
  );
}
