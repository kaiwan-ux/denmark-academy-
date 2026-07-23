"use client";

import { useRef, useState } from "react";
import { ArrowLeft, BookOpen, Headphones, PlayCircle, Radio } from "lucide-react";

type Track = "citizenship" | "pr";
type Recording = { title: string; src: string };

const citizenship: Recording[] = [
  ["Kapitel 1: Danmarks historie (del 1)", "chp-1-part-1"],
  ["Kapitel 1: Danmarks historie (del 2)", "chp-1-part-2"],
  ["Kapitel 2: Det danske demokrati", "chp-2"],
  ["Kapitel 3: Den danske økonomi", "chp-3"],
  ["Kapitel 4: Danmark og omverdenen", "chp-4"],
  ["Kapitel 5: Dansk kulturliv", "chp-5"],
  ["Kapitel 6: Temaopslag (del 1)", "chp-6-part-1"],
  ["Kapitel 6: Temaopslag (del 2)", "chp-6-part-2"],
].map(([title, file]) => ({ title, src: `/audio/citizenship/${file}.mp3` }));

const prTitles = [
  "Skole", "Uddannelse", "Dagtilbud", "Det danske arbejdsmarked", "Dansk erhvervsliv",
  "Det danske velfærdssamfund", "Familieliv", "Forenings- og fritidsliv", "Sundhed og sygdom",
  "Ligestilling", "Demokrati og grundloven", "Det danske retssamfund", "Folketing og regering",
  "Det lokale selvstyre", "Folkestyret i praksis – valg og partier", "Borgernes rettigheder og pligter",
  "Religion og kirke", "Danmark og omverdenen", "Danmarks geografi og befolkning",
  "Danmarks historie før 1945", "Danmarks historie efter 1945", "Dansk kultur", "Traditioner og mærkedage",
  "Danmarks forsvars- og sikkerhedspolitik", "Diskrimination, antisemitisme, hadforbrydelser og ekstremisme", "Klima",
];
const pr: Recording[] = [
  { title: "Indledning", src: "/audio/pr/mp-indledning.mp3" },
  ...prTitles.map((title, index) => ({ title: `Faktaark ${index + 1}: ${title}`, src: `/audio/pr/mp-faktaark-${index + 1}.mp3` })),
];

export default function AudioPage() {
  const [track, setTrack] = useState<Track | null>(null);
  const playing = useRef<HTMLAudioElement | null>(null);
  const recordings = track === "citizenship" ? citizenship : pr;
  function onPlay(event: React.SyntheticEvent<HTMLAudioElement>) {
    if (playing.current && playing.current !== event.currentTarget) playing.current.pause();
    playing.current = event.currentTarget;
  }
  return (
    <div className="audio-page" data-preserve-language>
      <section className="audio-hero">
        <div className="audio-eyebrow"><Headphones size={17} aria-hidden />LYDMATERIALE</div>
        <h1>Lyt til dit læremateriale.</h1>
        <p>Vælg først din prøvetype. Derefter kan du lytte til kapitlerne og faktaarkene på dansk.</p>
      </section>
      {!track ? (
        <section className="audio-track-section" aria-labelledby="choose-audio-track">
          <div className="audio-section-heading"><span>TRIN 1</span><h2 id="choose-audio-track">Hvilken prøve forbereder du dig til?</h2><p>Vælg en prøvetype for at se de tilhørende lydfiler.</p></div>
          <div className="audio-track-grid">
            <button type="button" onClick={() => setTrack("pr")}><span className="audio-track-icon"><Radio aria-hidden /></span><span><small>PERMANENT OPHOLD</small><strong>Medborgerskabsprøven</strong><em>Indledning og 26 faktaark</em></span><PlayCircle aria-hidden /></button>
            <button type="button" onClick={() => setTrack("citizenship")}><span className="audio-track-icon"><BookOpen aria-hidden /></span><span><small>DANSK STATSBORGERSKAB</small><strong>Indfødsretsprøven</strong><em>8 lyddele fordelt på 6 kapitler</em></span><PlayCircle aria-hidden /></button>
          </div>
        </section>
      ) : (
        <section className="audio-library">
          <button type="button" className="audio-back" onClick={() => { playing.current?.pause(); setTrack(null); }}><ArrowLeft size={17} aria-hidden />Vælg en anden prøvetype</button>
          <div className="audio-library-heading"><div><span>{track === "pr" ? "PERMANENT OPHOLD" : "DANSK STATSBORGERSKAB"}</span><h2>{track === "pr" ? "Medborgerskabsprøven" : "Indfødsretsprøven"}</h2></div><strong>{recordings.length} lydfiler</strong></div>
          <div className="audio-list">
            {recordings.map((recording, index) => <article className="audio-recording" key={recording.src}>
              <div className="audio-number">{String(index + 1).padStart(2, "0")}</div>
              <div className="audio-recording-copy"><span>LYDFIL {index + 1}</span><h3>{recording.title}</h3></div>
              <audio controls preload="metadata" onPlay={onPlay} aria-label={recording.title}><source src={recording.src} type="audio/mpeg" />Din browser understøtter ikke afspilning af lyd.</audio>
            </article>)}
          </div>
        </section>
      )}
    </div>
  );
}
