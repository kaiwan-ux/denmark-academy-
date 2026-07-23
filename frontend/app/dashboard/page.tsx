import { ArrowRight, BookOpen, Compass, GraduationCap, Library, Star, TimerReset } from "lucide-react";
import { CommandButton, GhostButton } from "@/components/ui";
import ScrollMorphHero from "@/components/ui/scroll-morph-hero";
import PassportBook from "@/components/ui/passport-book";

const studyPath = [
  {
    title: "Reading",
    description: "Official books stay organized by exam track.",
    icon: BookOpen,
    href: "/reader/demo"
  },
  {
    title: "Past Papers",
    description: "Practice with stored official-style questions.",
    icon: Library,
    href: "/practice"
  },
  {
    title: "Chapter Practice",
    description: "Practise verified questions chapter by chapter.",
    icon: GraduationCap,
    href: "/revision"
  },
  {
    title: "Current Affairs",
    description: "Review relevant updates for the citizenship test.",
    icon: Compass,
    href: "/current-affairs"
  },
  {
    title: "Mock Exam",
    description: "Rehearse timing, scoring, and exam pressure.",
    icon: TimerReset,
    href: "/exam-simulator"
  }
];

const bookPages = [
  "Read official material without losing your place.",
  "Practice questions are selected for your exam track.",
  "Revision returns to the ideas that need attention.",
  "Mock exams follow the real structure and timing."
];

const faqs = [
  {
    question: "Does Denmark Academy support both exams?",
    answer: "Yes. Permanent Residence and Citizenship preparation stay separated, so the material and questions do not mix."
  },
  {
    question: "Can I study from the official books?",
    answer: "Yes. The reading room keeps the official PDFs intact while letting students add private notes and highlights."
  },
  {
    question: "How does practice work?",
    answer: "Students can work through past-paper style questions, receive feedback, and continue toward timed mock exams."
  },
  {
    question: "Are mock exams realistic?",
    answer: "Mock exams follow the configured exam structure, timing, question counts, and passing logic for each track."
  }
];

const testimonials = [
  {
    name: "Maria Johansson",
    role: "Citizenship preparation",
    avatar: "MJ",
    rating: 5,
    text: "The study flow made every chapter feel manageable and the practice helped me understand the exam rhythm."
  },
  {
    name: "Rajesh Kumar",
    role: "Permanent Residence preparation",
    avatar: "RK",
    rating: 5,
    text: "Clear reading, focused revision, and mock exams gave me a simple way to prepare every day."
  },
  {
    name: "Anna Schmidt",
    role: "Citizenship preparation",
    avatar: "AS",
    rating: 5,
    text: "The platform feels calm and serious. It helped me know what to study next instead of guessing."
  },
  {
    name: "Michael Chen",
    role: "Permanent Residence preparation",
    avatar: "MC",
    rating: 4,
    text: "The practice and reading pages are well organized, and the exam simulation helped with time pressure."
  }
];

export default function DashboardPage() {
  return (
    <div className="space-y-24 pb-10">
      <ScrollMorphHero />
      <section className="lamp-hero motion-panel relative min-h-[680px] overflow-hidden rounded-[18px] border border-white/15 shadow-[0_44px_160px_rgba(87,0,18,0.42)]">
        <div className="lamp-aura" />
        <div className="lamp-beam lamp-beam-left" />
        <div className="lamp-beam lamp-beam-right" />
        <div className="ceiling-lamp" aria-hidden><span className="lamp-cord" /><span className="lamp-cap" /><span className="lamp-shade" /><span className="lamp-core" /></div>
        <div className="lamp-line" />
        <div className="hero-grid" />
        <div className="floating-pages" aria-hidden><span /><span /><span /></div>

        <div className="relative z-10 flex min-h-[680px] flex-col items-center justify-center px-5 py-20 text-center sm:px-10">
          <div className="motion-ink text-xs font-bold uppercase tracking-[0.36em] text-white/80">Denmark Academy</div>
          <h1 className="motion-ink mt-7 max-w-4xl text-4xl font-semibold leading-[1.12] tracking-tight text-white sm:text-6xl lg:text-7xl">
            Danish exam preparation with clarity and confidence.
          </h1>
          <p className="motion-ink mx-auto mt-6 max-w-2xl text-base leading-8 text-white/78 sm:text-xl">
            Official reading, focused practice, guided revision, and full exam rehearsal in one disciplined academy.
          </p>
          <div className="motion-ink mt-10 flex flex-wrap justify-center gap-3">
            <CommandButton href="/practice">Start practice</CommandButton>
            <GhostButton href="/reader/demo" icon={BookOpen}>Open reading room</GhostButton>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl text-center">
        <div className="motion-ink text-sm font-bold uppercase tracking-[0.3em] text-white/70">Your study journey</div>
        <h2 className="motion-ink mx-auto mt-5 max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">
          Five focused stages from first page to exam readiness.
        </h2>
      </section>

      <section className="mx-auto max-w-7xl">
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-5">
          {studyPath.map((step) => (
            <a key={step.title} href={step.href} className="motion-panel path-card group flex min-h-64 flex-col rounded-[14px] border border-white/14 p-6 transition-all relative overflow-hidden">
              {/* Book on the right side with DARK RED text */}
              <div className="absolute -right-2 -bottom-1 opacity-40 group-hover:opacity-60 transition-opacity pointer-events-none">
                <div className="relative" style={{width: '85px', height: '105px', transform: 'rotate(-8deg)'}}>
                  <div style={{
                    width: '100%',
                    height: '100%',
                    background: 'linear-gradient(90deg, rgba(255,255,255,0.7) 0%, rgba(255,255,255,0.95) 8%, rgba(255,255,255,0.8) 100%)',
                    borderRadius: '2px 8px 8px 2px',
                    boxShadow: 'inset 2px 0 6px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.15)',
                    position: 'relative'
                  }}>
                    {/* Book spine */}
                    <div style={{
                      position: 'absolute',
                      left: 0,
                      top: 0,
                      bottom: 0,
                      width: '9px',
                      background: 'linear-gradient(180deg, rgba(200,200,200,0.9), rgba(160,160,160,0.7))',
                      borderRadius: '2px 0 0 2px'
                    }} />
                    {/* Book text - DARK RED COLOR for maximum visibility */}
                    <div style={{
                      position: 'absolute',
                      top: '50%',
                      left: '50%',
                      transform: 'translate(-50%, -50%) rotate(-90deg)',
                      fontSize: '11px',
                      fontWeight: '900',
                      color: '#7f1d1d',
                      whiteSpace: 'nowrap',
                      letterSpacing: '1.2px',
                      textShadow: '0 1px 3px rgba(255,255,255,0.9), 0 0 1px rgba(255,255,255,0.5)'
                    }}>
                      {step.title.toUpperCase()}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex h-12 w-12 items-center justify-center rounded-[10px] bg-white text-[var(--red)] transition-all group-hover:scale-110 relative z-10">
                <step.icon size={22} aria-hidden />
              </div>
              <h3 className="mt-6 text-xl font-semibold text-white relative z-10">{step.title}</h3>
              <p className="mt-3 text-sm leading-6 text-white/72 relative z-10">{step.description}</p>
              <div className="mt-auto pt-5 opacity-0 transition-opacity group-hover:opacity-100 relative z-10">
                <ArrowRight size={18} className="text-white" />
              </div>
            </a>
          ))}
        </div>
      </section>

      <section className="book-showcase motion-panel relative overflow-hidden rounded-[22px] border border-white/14 px-6 py-16 shadow-[0_36px_140px_rgba(87,0,18,0.38)] sm:px-10 lg:px-14">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(255,255,255,0.2),transparent_30rem)]" />
        <div className="relative z-10 grid gap-12 lg:grid-cols-[0.88fr_1.12fr] lg:items-center">
          <div>
            <div className="text-sm font-bold uppercase tracking-[0.3em] text-white/70">Learning path</div>
            <h2 className="mt-4 text-4xl font-semibold leading-tight text-white sm:text-5xl">Progress should feel alive, not overwhelming.</h2>
            <p className="mt-5 max-w-xl text-lg leading-8 text-white/76">When you reach this point, the academy opens the next page: what to read, what to practice, and what to revise next.</p>
          </div>

          <PassportBook pages={bookPages} />
        </div>
      </section>

      <div className="section-intro motion-ink"><span className="text-sm font-bold uppercase tracking-[0.3em]">Exam readiness</span><h2>Build confidence before exam day.</h2><p>Measure your progress, strengthen weak areas, and practise under conditions designed to feel familiar.</p></div>

      <section className="motion-panel mx-auto max-w-4xl rounded-[18px] border border-white/14 px-6 py-12 text-center shadow-[0_28px_100px_rgba(87,0,18,0.28)]">
        <h2 className="mx-auto max-w-2xl text-3xl font-semibold leading-tight text-white sm:text-4xl">Exam confidence through structure, practice, and calm repetition.</h2>
        <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-white/76">Every lesson, question, and mock exam is designed to reduce stress and build mastery step by step.</p>
      </section>

      <section className="mx-auto max-w-7xl">
        <div className="motion-ink mb-10 text-center">
          <div className="text-sm font-bold uppercase tracking-[0.3em] text-white/70">Student results</div>
          <h2 className="mx-auto mt-5 max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">A serious preparation space students can trust.</h2>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {testimonials.map((testimonial) => (
            <article key={testimonial.name} className="motion-panel result-card flex flex-col rounded-[14px] border border-white/14 p-6 shadow-[0_20px_70px_rgba(87,0,18,0.22)] transition-all">
              <div className="mb-4 flex gap-1">
                {[...Array(5)].map((_, i) => (
                  <Star key={i} size={16} className={i < testimonial.rating ? "fill-[#fbbf24] text-[#fbbf24]" : "text-white/25"} />
                ))}
              </div>
              <p className="flex-1 text-sm leading-relaxed text-white/82">&quot;{testimonial.text}&quot;</p>
              <div className="mt-6 flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--red)] text-sm font-bold text-white shadow-lg">{testimonial.avatar}</div>
                <div>
                  <div className="text-sm font-semibold text-white">{testimonial.name}</div>
                  <div className="text-xs text-white/62">{testimonial.role}</div>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="faq-section mx-auto max-w-5xl pb-4">
        <div className="motion-ink mb-8 text-center">
          <div className="text-sm font-bold uppercase tracking-[0.3em] text-white/70">FAQ</div>
          <h2 className="mx-auto mt-5 max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">Questions students ask before they begin.</h2>
        </div>
        <div className="grid gap-4">
          {faqs.map((item) => (
            <details key={item.question} className="motion-panel faq-item group rounded-[14px] border border-white/14 p-5 shadow-[0_18px_60px_rgba(87,0,18,0.2)]">
              <summary className="cursor-pointer list-none text-lg font-semibold text-white marker:hidden [&::-webkit-details-marker]:hidden">
                <span className="flex items-center justify-between gap-4">
                  {item.question}
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[var(--red)] text-xl font-bold text-white transition group-open:rotate-45 shadow-lg">+</span>
                </span>
              </summary>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-white/76">{item.answer}</p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
