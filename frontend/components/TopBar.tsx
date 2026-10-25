"use client";

import { createContext, useContext } from "react";
import { useLang } from "@/lib/i18n";

/** Back to the start screen; null on the start screen itself. */
export const HomeContext = createContext<(() => void) | null>(null);

// The thin line at the top of every screen: the site's name (back to the
// start), what this screen is, then "my font" and the language switch in
// the corner. With the name, the screen's own item (back, its chapter) goes
// on a second row. `home={false}` where there's no room for the name (the
// drawing screen: its chapter list has it).
export function TopBar({ children, onFont, home = true }: { children?: React.ReactNode; onFont?: () => void; home?: boolean }) {
  const { lang, setLang, t } = useLang();
  const goHome = useContext(HomeContext);
  const name = home && goHome;
  return (
    <>
    <div className="topbar">
      <div className="topbar-left">
        {name ? (
          <button type="button" className="home-button" onClick={goHome} aria-label={t("কাকের ঠ্যাং: শুরুর পাতা", "Kaker Theng: start page")}>
            {t("কাকের ঠ্যাং", "Kaker Theng")}
          </button>
        ) : (
          children
        )}
      </div>
      <div className="topbar-right">
        {onFont && (
          <button type="button" className="button small" onClick={onFont}>
            {t("আমার ফন্ট", "My font")}
          </button>
        )}
        <div className="lang-switch" role="group" aria-label={t("ভাষা", "Language")}>
          <button type="button" lang="bn" aria-pressed={lang === "bn"} onClick={() => setLang("bn")}>
            বাংলা
          </button>
          <button type="button" lang="en" aria-pressed={lang === "en"} onClick={() => setLang("en")}>
            EN
          </button>
        </div>
      </div>
    </div>
    {name && children && <div className="topbar-sub">{children}</div>}
    </>
  );
}
