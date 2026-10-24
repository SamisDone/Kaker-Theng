"use client";

// One language on screen at a time: Bangla by default, English by the
// switch in the corner. Every piece of copy is written in both and picked
// here; the choice is remembered in this browser.

import { createContext, useContext, useEffect, useState } from "react";
import { bnNum } from "@/lib/bn";

export type UiLang = "bn" | "en";

const KEY = "kaker-theng-ui-lang";

type Ctx = { lang: UiLang; setLang: (l: UiLang) => void };

const LangContext = createContext<Ctx>({ lang: "bn", setLang: () => undefined });

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<UiLang>("bn");
  useEffect(() => {
    try {
      if (localStorage.getItem(KEY) === "en") setLangState("en");
    } catch {
      // blocked storage: Bangla
    }
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = (l: UiLang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      // fine: it only remembers the choice
    }
  };
  return <LangContext.Provider value={{ lang, setLang }}>{children}</LangContext.Provider>;
}

/** `t(bn, en)` picks the copy for the language on screen; `num` writes a
 *  number in its digits. */
export function useLang() {
  const { lang, setLang } = useContext(LangContext);
  return {
    lang,
    setLang,
    t: <T,>(bn: T, en: T): T => (lang === "bn" ? bn : en),
    num: (n: number | string) => (lang === "bn" ? bnNum(n) : String(n)),
  };
}
