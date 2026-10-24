"use client";

import { TopBar } from "@/components/TopBar";
import { useLang } from "@/lib/i18n";

// The first screen: the name, one line, and the two ways in. Once a font
// exists the name is written in the visitor's own hand.
export function StartScreen({ userFont, onDraw, onPaper, onFont }: { userFont: string | null; onDraw: () => void; onPaper: () => void; onFont?: () => void }) {
  const { t } = useLang();
  return (
    <div className="screen start-screen">
      <TopBar onFont={onFont} />
      <div className="start-body">
        <h1 key={userFont ?? "ui"} className={userFont ? "in-hand" : undefined} style={userFont ? { fontFamily: `"${userFont}", var(--bn)` } : undefined}>
          {t("কাকের ঠ্যাং", "Kaker Theng")}
        </h1>
        <p>{t("আপনার হাতের লেখা থেকে বাংলা আর ইংরেজি ফন্ট।", "A Bangla and English font from your handwriting.")}</p>
        <div className="start-buttons">
          <button type="button" className="button big primary" onClick={onDraw}>
            {t("আঁকুন", "Draw")}
          </button>
          <button type="button" className="button big" onClick={onPaper}>
            {t("কাগজে লিখুন", "Write on paper")}
          </button>
        </div>
      </div>
    </div>
  );
}
