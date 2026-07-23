"use client";

import { useEffect, useMemo, useState } from "react";

const topics = [
  "History",
  "Monarchy",
  "Democracy",
  "Geography",
  "Culture",
  "Welfare",
  "Community",
  "Rights",
  "Work",
  "Education",
  "Denmark",
  "Europe",
  "World",
  "Copenhagen",
  "Literature",
  "Architecture",
  "Science",
  "Equality",
  "Daily life",
  "Exam prep"
];

function coverSrc(index: number) {
  return `/books/covers/cover-${String(index + 1).padStart(2, "0")}.png`;
}

function BookCover({ topic, index, style }: { topic: string; index: number; style?: React.CSSProperties }) {
  const [loaded, setLoaded] = useState(false);
  return (
    <div className={`prompt-book ${loaded ? "is-cover-loaded" : "is-cover-loading"}`} style={style}>
      <div className="prompt-book-inner">
        <div className="prompt-book-face">
          <img
            src={coverSrc(index)}
            alt={`${topic} study book cover`}
            width={320}
            height={448}
            loading={index < 6 ? "eager" : "lazy"}
            fetchPriority={index < 4 ? "high" : "auto"}
            decoding="async"
            onLoad={() => setLoaded(true)}
          />
        </div>
        <div className="prompt-book-face prompt-book-back">
          <span>EXPLORE</span>
          <strong>{topic}</strong>
        </div>
      </div>
    </div>
  );
}

function StaticBookStage() {
  return (
    <div className="morph-stage is-static" aria-label="Danish citizenship book collection">
      {topics.map((topic, index) => (
        <BookCover
          key={topic}
          topic={topic}
          index={index}
          style={{
            transform: `translate3d(${(index - 9.5) * 44}px,80px,0) rotate(0deg)`,
            opacity: 1,
            transitionDelay: `${index * 18}ms`
          }}
        />
      ))}
    </div>
  );
}

export default function ScrollMorphHero() {
  const [phase, setPhase] = useState(0);
  const [morph, setMorph] = useState(0);
  const [size, setSize] = useState({ w: 1200, h: 720 });
  const [mounted, setMounted] = useState(false);
  const scatter = useMemo(
    () => topics.map((_, index) => ({ x: Math.sin(index * 47) * 850, y: Math.cos(index * 31) * 560, r: (index % 8 - 4) * 24 })),
    []
  );

  useEffect(() => {
    setMounted(true);
    topics.slice(0, 6).forEach((_, index) => {
      const image = new Image();
      image.decoding = "async";
      image.src = coverSrc(index);
    });
    const lineTimer = setTimeout(() => setPhase(1), 350);
    const arcTimer = setTimeout(() => setPhase(2), 1450);
    const update = () => {
      setSize({ w: window.innerWidth, h: window.innerHeight });
      setMorph(Math.max(0, Math.min(1, window.scrollY / 650)));
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      clearTimeout(lineTimer);
      clearTimeout(arcTimer);
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  return (
    <section className="library-hero prompt-hero">
      <div className="library-hero-copy">
        <div className="library-kicker">DANISH CITIZENSHIP · COMPLETE SYLLABUS</div>
        <h1>
          OFFICIAL MATERIAL.<br />
          <em>FOCUSED PRACTICE.</em>
        </h1>
      </div>
      {!mounted ? (
        <StaticBookStage />
      ) : (
        <div className="morph-stage" aria-label="Animated Danish citizenship book collection">
          {topics.map((topic, index) => {
            const circleAngle = (index / topics.length) * Math.PI * 2 - Math.PI / 2;
            const spread = Math.PI * 0.92;
            const arcAngle = -Math.PI / 2 - spread / 2 + (index / (topics.length - 1)) * spread;
            const radius = Math.min(size.w * 0.22, 215);
            const arcRadius = Math.min(size.w * 0.4, 460);
            const circle = { x: Math.cos(circleAngle) * radius, y: Math.sin(circleAngle) * radius + 30, r: (circleAngle * 180) / Math.PI + 90 };
            const arc = { x: Math.cos(arcAngle) * arcRadius, y: Math.sin(arcAngle) * arcRadius + 240, r: (arcAngle * 180) / Math.PI + 90 };
            const line = { x: (index - 9.5) * Math.min(46, size.w / 23), y: 80, r: 0 };
            const base = phase === 0 ? scatter[index] : phase === 1 ? line : circle;
            const pos = phase === 2
              ? { x: base.x + (arc.x - base.x) * morph, y: base.y + (arc.y - base.y) * morph, r: base.r + (arc.r - base.r) * morph }
              : base;
            return (
              <BookCover
                key={topic}
                topic={topic}
                index={index}
                style={{
                  transform: `translate3d(${pos.x.toFixed(2)}px,${pos.y.toFixed(2)}px,0) rotate(${pos.r.toFixed(2)}deg)`,
                  opacity: phase === 0 ? 0 : 1,
                  transitionDelay: `${index * 25}ms`
                }}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}
