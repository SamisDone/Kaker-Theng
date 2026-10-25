"use client";

import { useEffect, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { useLang } from "@/lib/i18n";
import { chromeIntent, inAppBrowser, isAndroid } from "@/lib/savefile";

// The first screen: the name, what you get and what it takes, and the ways
// in. Someone who has drawn before gets "continue" and their font first.
// Once their font writes the name fully (ঠ্য needs the ya-phala), the name
// is written in the visitor's own hand.
export function StartScreen(props: {
  userFont: string | null; // only once it writes "কাকের ঠ্যাং"
  progress: { drawn: number; total: number } | null; // a returning visitor's letters
  onDraw: () => void;
  onPaper: () => void;
  onFont?: () => void;
}) {
  const { t, num } = useLang();
  const { userFont, progress } = props;
  return (
    <div className="screen start-screen">
      <TopBar />
      <div className="start-body">
        <InAppWarning />
        <h1 key={userFont ?? "ui"} className={userFont ? "in-hand" : undefined} style={userFont ? { fontFamily: `"${userFont}", var(--bn)` } : undefined}>
          {t("কাকের ঠ্যাং", "Kaker Theng")}
        </h1>
        <p className="start-line">{t("আপনার হাতের লেখা থেকে বাংলা আর ইংরেজি ফন্ট।", "A Bangla and English font from your handwriting.")}</p>
        {progress ? (
          <>
            <p className="start-effort">
              {t(`${num(progress.total)}টার মধ্যে ${num(progress.drawn)}টা অক্ষর আঁকা হয়েছে।`, `${progress.drawn} of ${progress.total} letters drawn.`)}
            </p>
            <div className="start-buttons">
              <button type="button" className="button big primary" onClick={props.onDraw}>
                {t("আঁকা চালিয়ে যান →", "Continue drawing →")}
              </button>
              {props.onFont && (
                <button type="button" className="button big" onClick={props.onFont}>
                  {t("আমার ফন্ট", "My font")}
                </button>
              )}
            </div>
          </>
        ) : (
          <>
            <figure className="start-example">
              <img src="/kt/example.png" width={300} height={72} alt={t("হাতের লেখার একটা ফন্টে: আমার হাতের লেখা", "In a handwritten font: আমার হাতের লেখা")} />
            </figure>
            <p className="start-effort">{t("প্রায় ১৯০টা অক্ষর, ২০–৩০ মিনিট; যেকোনো সময় থামতে পারেন।", "About 190 letters, 20–30 minutes; stop any time.")}</p>
            <div className="start-buttons">
              <button type="button" className="button big primary" onClick={props.onDraw}>
                {t("আঁকুন", "Draw")}
              </button>
            </div>
          </>
        )}
        <p className="start-paper">
          <button type="button" className="link-button" onClick={props.onPaper}>
            {t("কাগজে লিখে ছবি দিতে চান?", "Rather write on paper and send photos?")}
          </button>
        </p>
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
