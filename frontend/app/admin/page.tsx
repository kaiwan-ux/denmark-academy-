import { Bell, CheckCircle2, FileCheck2, Gauge, Library, ShieldCheck } from "lucide-react";
import { CommandButton, InsightList, PageHeader, PaperStrip, SignalBadge, StudioSteps, Surface } from "@/components/ui";

export default function AdminPage() {
  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Review room" title="A quiet control desk for trusted learning content." description="New explanations, generated practice, source updates, and paper imports wait here until a human reviewer accepts them." action={<CommandButton href="/knowledge">Open source atelier</CommandButton>} />
      <section className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <Surface className="p-5">
          <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[#fff1d2]">Approval queue</h2><SignalBadge label="Needs review" /></div>
          <div className="grid gap-3">
            <PaperStrip title="Citizenship explanation draft" meta="Linked to one official question and two source passages." />
            <PaperStrip title="Permanent Residence practice draft" meta="Similar style, separate from official paper wording." />
            <PaperStrip title="Current affairs revision note" meta="Prepared from a trusted public source." />
          </div>
        </Surface>
        <Surface className="p-5">
          <h2 className="text-lg font-semibold text-[#fff1d2]">Health signals</h2>
          <StudioSteps steps={[
            { icon: CheckCircle2, title: "Official content", detail: "Protected from accidental edits.", state: "OK" },
            { icon: FileCheck2, title: "Answer links", detail: "Questions and answer keys stay paired.", state: "OK" },
            { icon: Gauge, title: "Search library", detail: "Learning sources are available for study support.", state: "OK" },
            { icon: Bell, title: "Notices", detail: "Reviewers are alerted when new work arrives.", state: "OK" }
          ]} />
        </Surface>
      </section>
      <Surface className="p-5"><InsightList items={["Reviewers can approve, reject, or ask for changes before students see generated content.", "Every approved item keeps its source trail.", "Official documents are versioned instead of overwritten."]} /></Surface>
    </div>
  );
}
