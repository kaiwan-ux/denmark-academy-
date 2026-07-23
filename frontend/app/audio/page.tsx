"use client";

import { useRef, useState } from "react";
import { ArrowLeft, BookOpen, Headphones, PlayCircle, Radio } from "lucide-react";
import { useLanguage } from "@/components/language-provider";

type Track = "citizenship" | "pr";
type Recording = { titleDa: string; titleEn: string; src: string };

const citizenship: Recording[] = [
  { titleDa: "Kapitel 1: Danmarks historie (del 1)", titleEn: "Chapter 1: Denmark's History (Part 1)", src: "/audio/citizenship/chp-1-part-1.mp3" },
  { titleDa: "Kapitel 1: Danmarks historie (del 2)", titleEn: "Chapter 1: Denmark's History (Part 2)", src: "/audio/citizenship/chp-1-part-2.mp3" },
  { titleDa: "Kapitel 2: Det danske demokrati", titleEn: "Chapter 2: Danish Democracy", src: "/audio/citizenship/chp-2.mp3" },
  { titleDa: "Kapitel 3: Den danske økonomi", titleEn: "Chapter 3: The Danish Economy", src: "/audio/citizenship/chp-3.mp3" },
  { titleDa: "Kapitel 4: Danmark og omverdenen", titleEn: "Chapter 4: Denmark and the World", src: "/audio/citizenship/chp-4.mp3" },
  { titleDa: "Kapitel 5: Dansk kulturliv", titleEn: "Chapter 5: Danish Cultural Life", src: "/audio/citizenship/chp-5.mp3" },
  { titleDa: "Kapitel 6: Temaopslag (del 1)", titleEn: "Chapter 6: Theme Topics (Part 1)", src: "/audio/citizenship/chp-6-part-1.mp3" },
  { titleDa: "Kapitel 6: Temaopslag (del 2)", titleEn: "Chapter 6: Theme Topics (Part 2)", src: "/audio/citizenship/chp-6-part-2.mp3" },
];

const prTopics = [
  { da: "Skole", en: "School" },
  { da: "Uddannelse", en: "Education" },
  { da: "Dagtilbud", en: "Childcare" },
  { da: "Det danske arbejdsmarked", en: "The Danish Labor Market" },
  { da: "Dansk erhvervsliv", en: "Danish Business Life" },
  { da: "Det danske velfærdssamfund", en: "The Danish Welfare Society" },
  { da: "Familieliv", en: "Family Life" },
  { da: "Forenings- og fritidsliv", en: "Associations and Leisure" },
  { da: "Sundhed og sygdom", en: "Health and Illness" },
  { da: "Ligestilling", en: "Equality" },
  { da: "Demokrati og grundloven", en: "Democracy and the Constitution" },
  { da: "Det danske retssamfund", en: "The Danish Legal System" },
  { da: "Folketing og regering", en: "Parliament and Government" },
  { da: "Det lokale selvstyre", en: "Local Self-Government" },
  { da: "Folkestyret i praksis – valg og partier", en: "Democracy in Practice – Elections and Parties" },
  { da: "Borgernes rettigheder og pligter", en: "Citizens' Rights and Duties" },
  { da: "Religion og kirke", en: "Religion and Church" },
  { da: "Danmark og omverdenen", en: "Denmark and the World" },
  { da: "Danmarks geografi og befolkning", en: "Denmark's Geography and Population" },
  { da: "Danmarks historie før 1945", en: "Denmark's History Before 1945" },
  { da: "Danmarks historie efter 1945", en: "Denmark's History After 1945" },
  { da: "Dansk kultur", en: "Danish Culture" },
  { da: "Traditioner og mærkedage", en: "Traditions and Holidays" },
  { da: "Danmarks forsvars- og sikkerhedspolitik", en: "Denmark's Defense and Security Policy" },
  { da: "Diskrimination, antisemitisme, hadforbrydelser og ekstremisme", en: "Discrimination, Antisemitism, Hate Crimes and Extremism" },
  { da: "Klima", en: "Climate" },
];

const pr: Recording[] = [
  { titleDa: "Indledning", titleEn: "Introduction", src: "/audio/pr/mp-indledning.mp3" },
  ...prTopics.map((topic, index) => ({
    titleDa: `Faktaark ${index + 1}: ${topic.da}`,
    titleEn: `Fact Sheet ${index + 1}: ${topic.en}`,
    src: `/audio/pr/mp-faktaark-${index + 1}.mp3`
  })),
];

export default function AudioPage() {
  const [track, setTrack] = useState<Track | null>(null);
  const playing = useRef<HTMLAudioElement | null>(null);
  const { language } = useLanguage();
  const recordings = track === "citizenship" ? citizenship : pr;
  
  function onPlay(event: React.SyntheticEvent<HTMLAudioElement>) {
    if (playing.current && playing.current !== event.currentTarget) playing.current.pause();
    playing.current = event.currentTarget;
  }
  
  return (
    <div className="audio-page">
      <section className="audio-hero">
        <div className="audio-eyebrow">
          <Headphones size={17} aria-hidden />
          {language === "da" ? "LYDMATERIALE" : "AUDIO MATERIAL"}
        </div>
        <h1>{language === "da" ? "Lyt til dit læremateriale." : "Listen to your learning material."}</h1>
        <p>
          {language === "da" 
            ? "Vælg først din prøvetype. Derefter kan du lytte til kapitlerne og faktaarkene på dansk."
            : "First choose your exam type. Then you can listen to the chapters and fact sheets in Danish."}
        </p>
      </section>
      {!track ? (
        <section className="audio-track-section" aria-labelledby="choose-audio-track">
          <div className="audio-section-heading">
            <span>{language === "da" ? "TRIN 1" : "STEP 1"}</span>
            <h2 id="choose-audio-track">
              {language === "da" ? "Hvilken prøve forbereder du dig til?" : "Which exam are you preparing for?"}
            </h2>
            <p>
              {language === "da" 
                ? "Vælg en prøvetype for at se de tilhørende lydfiler."
                : "Select an exam type to see the corresponding audio files."}
            </p>
          </div>
          <div className="audio-track-grid">
            <button type="button" onClick={() => setTrack("pr")}>
              <span className="audio-track-icon"><Radio aria-hidden /></span>
              <span>
                <small>{language === "da" ? "PERMANENT OPHOLD" : "PERMANENT RESIDENCE"}</small>
                <strong>{language === "da" ? "Medborgerskabsprøven" : "Citizenship Test"}</strong>
                <em>{language === "da" ? "Indledning og 26 faktaark" : "Introduction and 26 fact sheets"}</em>
              </span>
              <PlayCircle aria-hidden />
            </button>
            <button type="button" onClick={() => setTrack("citizenship")}>
              <span className="audio-track-icon"><BookOpen aria-hidden /></span>
              <span>
                <small>{language === "da" ? "DANSK STATSBORGERSKAB" : "DANISH CITIZENSHIP"}</small>
                <strong>{language === "da" ? "Indfødsretsprøven" : "Naturalization Test"}</strong>
                <em>{language === "da" ? "8 lyddele fordelt på 6 kapitler" : "8 audio parts across 6 chapters"}</em>
              </span>
              <PlayCircle aria-hidden />
            </button>
          </div>
        </section>
      ) : (
        <section className="audio-library">
          <button type="button" className="audio-back" onClick={() => { playing.current?.pause(); setTrack(null); }}>
            <ArrowLeft size={17} aria-hidden />
            {language === "da" ? "Vælg en anden prøvetype" : "Choose a different exam type"}
          </button>
          <div className="audio-library-heading">
            <div>
              <span>
                {track === "pr" 
                  ? (language === "da" ? "PERMANENT OPHOLD" : "PERMANENT RESIDENCE")
                  : (language === "da" ? "DANSK STATSBORGERSKAB" : "DANISH CITIZENSHIP")}
              </span>
              <h2>
                {track === "pr"
                  ? (language === "da" ? "Medborgerskabsprøven" : "Citizenship Test")
                  : (language === "da" ? "Indfødsretsprøven" : "Naturalization Test")}
              </h2>
            </div>
            <strong>
              {recordings.length} {language === "da" ? "lydfiler" : "audio files"}
            </strong>
          </div>
          <div className="audio-list">
            {recordings.map((recording, index) => {
              const title = language === "da" ? recording.titleDa : recording.titleEn;
              return (
                <article className="audio-recording" key={recording.src}>
                  <div className="audio-number">{String(index + 1).padStart(2, "0")}</div>
                  <div className="audio-recording-copy">
                    <span>
                      {language === "da" ? "LYDFIL" : "AUDIO FILE"} {index + 1}
                    </span>
                    <h3>{title}</h3>
                  </div>
                  <audio controls preload="metadata" onPlay={onPlay} aria-label={title}>
                    <source src={recording.src} type="audio/mpeg" />
                    {language === "da" 
                      ? "Din browser understøtter ikke afspilning af lyd."
                      : "Your browser does not support audio playback."}
                  </audio>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
