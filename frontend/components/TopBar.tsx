"use client";

import { useLang } from "@/lib/i18n";

// The thin line at the top of every screen: what this screen is on the
// left; "my font" and the language switch in the corner.
export function TopBar({ children, onFont }: { children?: React.ReactNode; onFont?: () => void }) {
  const { lang, setLang, t } = useLang();
  return (
    <div className="topbar">
      <div className="topbar-left">{children}</div>
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
  );
}
