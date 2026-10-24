"use client";

import { TopBar } from "@/components/TopBar";
import { type Chapter } from "@/lib/chapters";
import { pct } from "@/lib/bn";
import { useLang } from "@/lib/i18n";

// Missing letters in the sample show as faint boxes from this font
// (public/kt/missing.woff2), never in another typeface.
export const MISSING_FONT = '"KT Missing"';

// After a chapter: how much the font can write now, and a line in it.
export function RewardScreen(props: {
  chapter: Chapter;
  next: Chapter | null; // the next chapter with letters left
  drawn: number;
  total: number;
  words: number | null; // share of Bangla words, once the server has built the font
  building: boolean;
  userFont: string | null;
  note: string | null;
  onContinue: () => void;
  onFont: () => void;
}) {
  const { t, num } = useLang();
  const { chapter, next } = props;
  const english = chapter.id === "english";
  const font = props.userFont ? `"${props.userFont}", ${MISSING_FONT}` : MISSING_FONT;
  return (
    <div className="screen reward-screen">
      <TopBar onFont={props.onFont} />
      <div className="reward-body">
        <h2>{t(`${chapter.name[0]} হয়ে গেল`, `${chapter.name[1]}: done`)}</h2>
        <p className="mono pencil">
          {t(`${num(props.total)}টার মধ্যে ${num(props.drawn)}টা আঁকা`, `${props.drawn} of ${props.total} drawn`)}
        </p>
        <div className="reward-number" aria-live="polite">
          {english ? null : props.words !== null && !props.building ? (
            <>
              <strong>{num(pct(props.words))}%</strong>
              <span>{t("বাংলা শব্দ এখন আপনার ফন্টে লেখা যায়", "of Bangla words can now be written in your font")}</span>
            </>
          ) : props.building ? (
            <span>{t("আপনার ফন্ট বানাচ্ছি…", "making your font…")}</span>
          ) : null}
        </div>
        {props.note && <p className="margin-note">{props.note}</p>}
        <p className="reward-sample" lang={english ? "en" : "bn"} style={{ fontFamily: font }}>
          {chapter.sample}
        </p>
        <p className="pencil small-note">{t("ধূসর ঘর: যে অক্ষর এখনও আঁকা হয়নি।", "Grey boxes: letters not drawn yet.")}</p>
        <div className="card-buttons">
          {next && (
            <button type="button" className="button big primary" onClick={props.onContinue}>
              {t(`চালিয়ে যান: ${next.name[0]} →`, `Continue: ${next.name[1]} →`)}
            </button>
          )}
          <button type="button" className={`button big${next ? "" : " primary"}`} onClick={props.onFont}>
            {t("আমার ফন্ট", "My font")}
          </button>
        </div>
      </div>
    </div>
  );
}
