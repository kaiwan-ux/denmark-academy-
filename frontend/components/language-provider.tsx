"use client";

import { createContext, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from "react";
import { interfaceTranslations } from "@/lib/interface-translations";

export type InterfaceLanguage = "en" | "da";
const reverseTranslations = Object.fromEntries(Object.entries(interfaceTranslations).map(([english, danish]) => [danish, english]));

function translateDynamic(value: string, language: InterfaceLanguage): string {
  const direct = language === "da" ? interfaceTranslations[value] : reverseTranslations[value];
  if (direct) return direct;
  if (language === "da") {
    const patterns: Array<[RegExp, (...parts: string[]) => string]> = [
      [/^(\d+) answered$/, (count) => count + " besvaret"],
      [/^(\d+) attempted · (\d+)% accuracy$/, (count, percent) => count + " forsøgt · " + percent + "% nøjagtighed"],
      [/^(\d+) of (\d+) completed · Next item (\d+)$/, (done, total, next) => done + " af " + total + " gennemført · Næste emne " + next],
      [/^(\d+) min$/, (count) => count + " min"]
    ];
    for (const [pattern, replacement] of patterns) {
      const match = value.match(pattern);
      if (match) return replacement(...match.slice(1));
    }
  } else {
    const patterns: Array<[RegExp, (...parts: string[]) => string]> = [
      [/^(\d+) besvaret$/, (count) => count + " answered"],
      [/^(\d+) forsøgt · (\d+)% nøjagtighed$/, (count, percent) => count + " attempted · " + percent + "% accuracy"],
      [/^(\d+) af (\d+) gennemført · Næste emne (\d+)$/, (done, total, next) => done + " of " + total + " completed · Next item " + next]
    ];
    for (const [pattern, replacement] of patterns) {
      const match = value.match(pattern);
      if (match) return replacement(...match.slice(1));
    }
  }
  return value;
}

function isPreserved(node: Node) {
  const element = node.nodeType === Node.ELEMENT_NODE ? node as Element : node.parentElement;
  return Boolean(element?.closest("[data-preserve-language], .notranslate, script, style, code, iframe"));
}

function translateText(node: Text, language: InterfaceLanguage) {
  const raw = node.nodeValue ?? "";
  const match = raw.match(/^(\s*)([\s\S]*?)(\s*)$/);
  if (!match || !match[2]) return;
  const translated = translateDynamic(match[2], language);
  if (translated !== match[2]) node.nodeValue = match[1] + translated + match[3];
}

function translateAttributes(element: Element, language: InterfaceLanguage) {
  for (const attribute of ["placeholder", "aria-label", "title"]) {
    const value = element.getAttribute(attribute);
    if (!value) continue;
    const translated = translateDynamic(value, language);
    if (translated !== value) element.setAttribute(attribute, translated);
  }
}

function translateTree(root: Node, language: InterfaceLanguage) {
  if (isPreserved(root)) return;
  if (root.nodeType === Node.TEXT_NODE) {
    translateText(root as Text, language);
    return;
  }
  if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return;
  if (root.nodeType === Node.ELEMENT_NODE) translateAttributes(root as Element, language);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let current = walker.nextNode();
  while (current) {
    if (!isPreserved(current)) {
      if (current.nodeType === Node.TEXT_NODE) translateText(current as Text, language);
      else translateAttributes(current as Element, language);
    }
    current = walker.nextNode();
  }
}

type LanguageContextValue = {
  language: InterfaceLanguage;
  setLanguage: (language: InterfaceLanguage) => void;
  t: (english: string) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<InterfaceLanguage>("da");
  useLayoutEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dataset.interfaceLanguage = language;
    translateTree(document.body, language);
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === "characterData") translateTree(mutation.target, language);
        mutation.addedNodes.forEach((node) => translateTree(node, language));
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => ({
    language,
    setLanguage,
    t: (english) => language === "da" ? interfaceTranslations[english] ?? english : english
  }), [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("useLanguage must be used inside LanguageProvider");
  return value;
}


