"use client";

import { useEffect, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { useLang } from "@/lib/i18n";
import { chromeIntent, inAppBrowser, isAndroid } from "@/lib/savefile";

// The first screen: the name, one line, and the two ways in. Once a font
// exists the name is written in the visitor's own hand.
export function StartScreen({ userFont, onDraw, onPaper, onFont }: { userFont: string | null; onDraw: () => void; onPaper: () => void; onFont?: () => void }) {
  const { t } = useLang();
  return (
    <div className="screen start-screen">
      <TopBar onFont={onFont} />
      <div className="start-body">
        <InAppWarning />
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

// Inside Facebook's or Messenger's own browser the drawing is kept where
// Chrome can't see it, and nothing can be saved: say so before any drawing.
function InAppWarning() {
  const { t } = useLang();
  const [inApp, setInApp] = useState<{ app: string; android: boolean } | null>(null);
  useEffect(() => {
    const app = inAppBrowser();
    if (app !== null) setInApp({ app, android: isAndroid() });
  }, []);
  if (!inApp) return null;
  const app = inApp.app || t("একটা অ্যাপ", "an app");
  return (
    <div className="in-app-warning" role="note">
      <p className="margin-note">
        {t(
          `আপনি ${app}-এর ভেতরের ব্রাউজারে আছেন। আঁকা হারিয়ে যেতে পারে, আগে Chrome-এ খুলুন।`,
          `You're inside ${inApp.app ? `${inApp.app}'s` : "an app's"} browser. Open in Chrome first so your drawing isn't lost.`,
        )}
      </p>
      {inApp.android ? (
        <a className="button primary" href={chromeIntent()}>
          {t("Chrome-এ খুলুন", "Open in Chrome")}
        </a>
      ) : (
        <p>{t("⋯ মেনু থেকে “ব্রাউজারে খুলুন” চাপুন।", "Use the ⋯ menu: “Open in browser”.")}</p>
      )}
    </div>
  );
}
