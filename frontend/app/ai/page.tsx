import { BadgeCheck, BrainCircuit, FileText, ShieldCheck, Sparkles } from "lucide-react";
import { CommandButton, InsightList, PageHeader, SignalBadge, StudioSteps, Surface } from "@/components/ui";

export default function AIPage() {
  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Study intelligence" title="A mentor layer that supports the lesson, not replaces it." description="The platform can explain, summarize, recommend, and create practice drafts while keeping official learning material protected and reviewable." action={<CommandButton href="/mentor">Open mentor</CommandButton>} />
      <section className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <Surface className="p-5">
          <div className="mb-5 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-[#fff1d2]">Intelligence rooms</h2>
            <SignalBadge label="Guided" />
          </div>
          <StudioSteps steps={[
            { icon: BrainCircuit, title: "Mentor desk", detail: "Answers questions with the right source and the student's level in mind.", state: "Teach" },
            { icon: FileText, title: "Explanation studio", detail: "Turns difficult official questions into clear approved explanations.", state: "Clarify" },
            { icon: Sparkles, title: "Practice maker", detail: "Creates draft questions, notes, flashcards, and study tasks for review.", state: "Create" },
            { icon: ShieldCheck, title: "Quality room", detail: "Checks whether learning content is helpful, fair, and source-backed.", state: "Protect" }
          ]} />
        </Surface>
        <Surface className="p-5">
          <h2 className="text-lg font-semibold text-[#fff1d2]">How a new explanation reaches students</h2>
          <div className="mt-5 grid gap-3">
            {["Find the right source", "Match the student's level", "Write a clear draft", "Check quality and overlap", "Send for review", "Publish when approved"].map((step, index) => (
              <div key={step} className="motion-panel flex items-center gap-3 rounded-[9px] border border-brass/20 bg-white/[0.035] p-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brass text-sm font-semibold text-[#160a05]">{index + 1}</span>
                <span className="font-medium text-[#fff1d2]">{step}</span>
              </div>
            ))}
          </div>
        </Surface>
      </section>
      <Surface className="p-5">
        <div className="grid gap-5 lg:grid-cols-[0.7fr_1.3fr] lg:items-center">
          <div className="flex items-center gap-3"><BadgeCheck className="text-brass" aria-hidden /><h2 className="text-xl font-semibold text-[#fff1d2]">Not a chatbot</h2></div>
          <InsightList items={["The mentor is designed to improve learning actions inside the academy.", "Created questions are clearly separate from official past-paper questions.", "Mock composition respects exam structure and the selected study mode."]} />
        </div>
      </Surface>
    </div>
  );
}
