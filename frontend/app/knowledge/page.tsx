import { Bell, FileStack, Globe2, Library, Newspaper, ShieldCheck } from "lucide-react";
import { CommandButton, InsightList, PageHeader, PaperStrip, SignalBadge, StudioSteps, Surface } from "@/components/ui";

export default function KnowledgePage() {
  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Source atelier" title="A living library that keeps itself organized." description="Official sites, PDFs, public notices, and uploaded papers can be collected, cleaned, checked, and prepared for student learning without manual chaos." action={<CommandButton href="/admin">Review new work</CommandButton>} />
      <section className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <Surface className="p-5">
          <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[#fff1d2]">Source shelves</h2><SignalBadge label="Traceable" /></div>
          <div className="grid gap-3">
            <PaperStrip title="Official government pages" meta="Tracked with source dates and review status." />
            <PaperStrip title="Exam book PDFs" meta="Prepared for reading, practice, and mentor support." />
            <PaperStrip title="Current affairs notes" meta="Collected only when relevant to exam preparation." />
          </div>
        </Surface>
        <Surface className="p-5">
          <h2 className="text-lg font-semibold text-[#fff1d2]">Content journey</h2>
          <StudioSteps steps={[
            { icon: Globe2, title: "Collect trusted sources", detail: "Official websites, PDFs, feeds, and manual uploads enter one review path.", state: "Find" },
            { icon: FileStack, title: "Prepare the document", detail: "Text is cleaned, divided into useful passages, and labeled for learning.", state: "Prepare" },
            { icon: ShieldCheck, title: "Check quality", detail: "Duplicates, missing source details, and weak drafts are flagged before publication.", state: "Check" },
            { icon: Bell, title: "Notify reviewers", detail: "The right person sees new work when it needs a decision.", state: "Alert" }
          ]} />
        </Surface>
      </section>
      <Surface className="p-5">
        <div className="grid gap-5 lg:grid-cols-[0.7fr_1.3fr] lg:items-center">
          <div className="flex items-center gap-3"><Newspaper className="text-brass" aria-hidden /><h2 className="text-xl font-semibold text-[#fff1d2]">Current affairs, carefully handled</h2></div>
          <InsightList items={["Relevant Danish news can become summaries, flashcards, notes, and practice drafts.", "Generated study content waits for approval before students see it.", "Official documents are preserved with version history and source trails."]} />
        </div>
      </Surface>
    </div>
  );
}
