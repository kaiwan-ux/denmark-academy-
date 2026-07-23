"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { useLanguage } from "@/components/language-provider";

export default function PassportBook({ pages }: { pages: string[] }) {
  const { t } = useLanguage();
  const sceneRef = useRef<HTMLDivElement>(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setIsOpen(true);
      return;
    }

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        window.requestAnimationFrame(() => window.requestAnimationFrame(() => setIsOpen(true)));
      } else if (entry.boundingClientRect.top > 0) {
        setIsOpen(false);
      }
    }, { threshold: 0.35, rootMargin: "0px 0px -12% 0px" });

    observer.observe(scene);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={sceneRef} className={`passport-scroll-scene ${isOpen ? "is-open" : ""}`} aria-label={t("Animated Danish passport")}>
      <div className="passport-book">
        <div className="passport-pages">
          <section className="passport-page passport-page-left">
            <div className="passport-page-rule" />
            <h3>{t("Study record")}</h3>
            <p>{t("Reading, practice, revision, and exam rehearsal stay connected.")}</p>
          </section>
          <section className="passport-page passport-page-right">
            <div className="passport-page-rule" />
            <h3>{t("Next page")}</h3>
            <ul>{pages.map((item) => <li key={item}>{t(item)}</li>)}</ul>
          </section>
          <span className="passport-centre-fold" aria-hidden />
        </div>
        <div className="passport-cover" aria-hidden>
          <Image src="/image.PNG" alt="" fill sizes="(max-width: 700px) 78vw, 340px" priority className="passport-cover-image" />
          <span className="passport-cover-edge" />
        </div>
      </div>
    </div>
  );
}
