"use client";

import { useEffect } from "react";

type AnimeModule = {
  animate?: (targets: string | Element | Element[], params: Record<string, unknown>) => unknown;
  stagger?: (value: number, params?: Record<string, unknown>) => unknown;
  random?: (min: number, max: number, decimals?: number) => number;
};

export function LibraryMotion() {
  useEffect(() => {
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    document.documentElement.classList.add("motion-js");

    async function run() {
      try {
        const mod = (await import("animejs")) as AnimeModule;
        if (cancelled) return;
        const animate = mod.animate;
        if (!animate) {
          document.documentElement.classList.add("motion-ready");
          return;
        }

        const stagger = mod.stagger ?? ((value: number) => (_: unknown, index: number) => index * value);
        const play = (targets: string, params: Record<string, unknown>) => {
          if (document.querySelector(targets)) animate(targets, params);
        };

        document.documentElement.classList.add("motion-ready");

        play(".site-header", { opacity: [0, 1], translateY: [-18, 0], duration: 720, easing: "easeOutCubic" });
        play(".brand-mark", { opacity: [0, 1], translateX: [-10, 0], duration: 650, easing: "easeOutQuad" });
        play(".nav-word", { opacity: [0, 1], translateY: [-8, 0], duration: 600, delay: stagger(32), easing: "easeOutQuad" });
        play(".motion-panel", { opacity: [0, 1], translateY: [26, 0], duration: 820, delay: stagger(55), easing: "easeOutCubic" });
        play(".motion-ink", { opacity: [0, 1], translateY: [18, 0], duration: 760, delay: stagger(46), easing: "easeOutQuad" });
        play(".motion-stat", { opacity: [0, 1], translateY: [18, 0], scale: [0.96, 1], duration: 760, delay: stagger(90), easing: "easeOutBack" });
        play(".motion-book", { opacity: [0, 1], translateY: [22, 0], rotate: () => [mod.random ? mod.random(-2, 2, 2) : -1, 0], duration: 900, delay: stagger(38), easing: "easeOutCubic" });
        play(".motion-map", { opacity: [0, 1], translateY: [18, 0], duration: 1100, delay: stagger(120), easing: "easeOutExpo" });

        play(".ceiling-lamp", { opacity: [0, 1], top: ["-6rem", "0rem"], duration: 1050, delay: 80, easing: "easeOutExpo" });
        play(".lamp-shade", { rotate: [-2.5, 0], duration: 1300, delay: 140, easing: "easeOutElastic" });
        play(".lamp-core", { opacity: [0.35, 1], scaleX: [0.62, 1], alternate: true, loop: true, duration: 2400, easing: "easeInOutSine" });
        play(".lamp-beam-left", { opacity: [0.44, 0.9], scaleX: [0.5, 1], duration: 1200, delay: 240, easing: "easeInOutCubic" });
        play(".lamp-beam-right", { opacity: [0.44, 0.9], scaleX: [0.5, 1], duration: 1200, delay: 240, easing: "easeInOutCubic" });
        play(".lamp-line", { opacity: [0, 1], scaleX: [0.18, 1], duration: 1050, delay: 140, easing: "easeOutExpo" });
        play(".lamp-aura", { opacity: [0.46, 0.72], scale: [0.94, 1.04], alternate: true, loop: true, duration: 3600, easing: "easeInOutSine" });
        play(".floating-pages span", { opacity: [0, 1], translateY: [18, 0], rotate: () => [mod.random ? mod.random(-12, 12, 1) : -6, mod.random ? mod.random(-4, 4, 1) : 0], duration: 1100, delay: stagger(160), easing: "easeOutCubic" });
        play(".floating-pages span", { translateY: [0, -10], alternate: true, loop: true, duration: 4200, delay: stagger(260), easing: "easeInOutSine" });
        play(".lamp-glow", { opacity: [0.34, 0.7], scaleX: [0.94, 1.06], scaleY: [0.96, 1.02], alternate: true, loop: true, duration: 3000, easing: "easeInOutSine" });

        const bookShowcase = document.querySelector(".book-showcase");
        if (bookShowcase) {
          let playedBook = false;
          const observer = new IntersectionObserver((entries) => {
            if (playedBook || !entries.some((entry) => entry.isIntersecting)) return;
            playedBook = true;
            play(".academy-book", { opacity: [0, 1], translateY: [42, 0], rotateX: [10, 0], duration: 950, easing: "easeOutExpo" });
            play(".book-left", { rotateY: [-8, 0], duration: 1050, delay: 120, easing: "easeOutCubic" });
            play(".book-right", { rotateY: [8, 0], duration: 1050, delay: 120, easing: "easeOutCubic" });
            play(".turning-page", { rotateY: [0, 178], translateX: [0, 12], opacity: [1, 0.92], duration: 1750, delay: 520, easing: "easeInOutCubic" });
            play(".book-page li", { opacity: [0, 1], translateX: [-10, 0], duration: 580, delay: stagger(115, { start: 1320 }), easing: "easeOutQuad" });
            observer.disconnect();
          }, { threshold: 0.34 });
          observer.observe(bookShowcase);
        }

        const hero = document.querySelector(".hero-parallax, .lamp-hero");
        if (hero) {
          const onMove = (event: Event) => {
            const pointer = event as PointerEvent;
            const rect = (hero as HTMLElement).getBoundingClientRect();
            const x = ((pointer.clientX - rect.left) / rect.width - 0.5) * 12;
            const y = ((pointer.clientY - rect.top) / rect.height - 0.5) * 8;
            const pages = Array.from(hero.querySelectorAll(".floating-pages span"));
            if (pages.length) animate(pages, { translateX: x, translateY: y, duration: 900, easing: "easeOutQuad" });
            const line = hero.querySelector(".lamp-line");
            if (line) animate(line, { translateX: x * 0.18, duration: 900, easing: "easeOutQuad" });
          };
          hero.addEventListener("pointermove", onMove);
          cleanup = () => hero.removeEventListener("pointermove", onMove);
        }
      } catch (error) {
        console.warn("Library motion disabled; showing static UI", error);
        document.documentElement.classList.add("motion-ready");
      }
    }

    void run();
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, []);

  return null;
}



