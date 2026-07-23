import { BookOpen, FileQuestion, Library, Search, ShieldCheck } from "lucide-react";
import { CommandButton, InsightList, PageHeader, PaperStrip, SignalBadge, StudioSteps, Surface } from "@/components/ui";

export default function SearchPage() {
  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Evidence finder" title="Find the source before asking for help." description="Search official reading, past-paper questions, answers, approved explanations, and current study notes while keeping each exam track separate." action={<CommandButton href="/mentor">Ask with source</CommandButton>} />
      <section className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <Surface className="p-5">
          <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[#fff1d2]">Search desk</h2><SignalBadge label="Citizenship" /></div>
          <div className="flex gap-3 rounded-[10px] border border-brass/20 bg-[#100703] p-3">
            <Search className="mt-1 text-brass" size={20} aria-hidden />
            <div className="min-w-0 flex-1 text-[#d6bf98]">Search for parliament, rights, residence requirements, answer explanations...</div>
          </div>
          <div className="mt-5 grid gap-3">
            <PaperStrip title="Reading passage: Parliament" meta="Citizenship reading room, chapter one." />
            <PaperStrip title="Official question: Parliament role" meta="Past paper answer linked and ready for practice." />
            <PaperStrip title="Approved explanation: law-making" meta="Reviewed learning note for a common mistake." />
          </div>
        </Surface>
        <Surface className="p-5">
          <h2 className="text-lg font-semibold text-[#fff1d2]">Search rules</h2>
          <StudioSteps steps={[
            { icon: ShieldCheck, title: "Keep tracks separate", detail: "Residence and Citizenship results never blend by accident.", state: "Protect" },
            { icon: Library, title: "Prefer trusted sources", detail: "Official material and approved explanations appear first.", state: "Rank" },
            { icon: FileQuestion, title: "Connect answers", detail: "Question results keep their answer key nearby.", state: "Pair" },
            { icon: BookOpen, title: "Support reading", detail: "Results can open directly in the reading room.", state: "Open" }
          ]} />
        </Surface>
      </section>
      <Surface className="p-5"><InsightList items={["Students can verify a mentor answer by opening the source.", "Search is useful for quick revision before a mock.", "Current affairs notes appear only when they are relevant to the selected track."]} /></Surface>
    </div>
  );
}
