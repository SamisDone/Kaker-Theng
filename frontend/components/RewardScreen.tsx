"use client";

import { TopBar } from "@/components/TopBar";
import { type Chapter } from "@/lib/chapters";
import { pct } from "@/lib/bn";
import { useLang } from "@/lib/i18n";

// Missing letters in the sample show as faint boxes from this font
// (public/kt/missing.woff2), never in another typeface.
export const MISSING_FONT = '"KT Missing"';

// Below this share of words the percentage says little ("2%"): the letters
// drawn and a word the font already writes say more.
const WORDS_MEANINGFUL = 0.1;

/** A word to show off: the longest of the most common ones the font writes. */
export function showWord(words: string[]): string | null {
  const top = words.slice(0, 20);
  return top.length ? top.reduce((a, b) => (b.length > a.length ? b : a)) : null;
}

// After a chapter: what was drawn (and what was skipped), and what the font
// can write now.
export function RewardScreen(props: {
  chapter: Chapter;
  next: Chapter | null; // the next chapter with letters left
  drawn: number;
  total: number;
  progress: { drawn: number; total: number }; // every chapter
  words: number | null; // share of Bangla words, once the server has built the font
  writable: string[]; // common words the font writes, most common first
  building: boolean;
  userFont: string | null;
  note: string | null;
  onContinue: () => void;
  onSkipped: () => void; // draw the ones skipped in this chapter
  onFont: () => void;
}) {
  const { t, num } = useLang();
  const { chapter, next, drawn, total } = props;
  const english = chapter.id === "english";
  const font = props.userFont ? `"${props.userFont}", ${MISSING_FONT}` : MISSING_FONT;
  const left = total - drawn;
  const word = english ? null : showWord(props.writable);
  const known = props.words !== null && !props.building;
  const few = !known || props.words! < WORDS_MEANINGFUL;
  return (
    <div className="screen reward-screen">
      <TopBar onFont={props.onFont} />
      <div className="reward-body">
        <h2>{left ? t(`${num(drawn)}টা আঁকা, ${num(left)}টা বাকি`, `${drawn} drawn, ${left} left`) : t(`${chapter.name[0]} হয়ে গেল`, `${chapter.name[1]}: done`)}</h2>
        {left > 0 && (
          <p>
            <button type="button" className="button" onClick={props.onSkipped}>
              {t(`বাদ পড়া ${num(left)}টা আঁকুন`, `Draw the ${left} skipped`)}
            </button>
          </p>
        )}
        <div className="reward-number" aria-live="polite">
          {english ? null : few ? (
            <>
              <strong>
                {num(props.progress.drawn)}
                <span className="reward-of">/{num(props.progress.total)}</span>
              </strong>
              <span>{t("অক্ষর আঁকা হয়েছে", "letters drawn")}</span>
            </>
          ) : (
            <>
              <strong>{num(pct(props.words!))}%</strong>
              <span>{t("বাংলা শব্দ এখন আপনার ফন্টে লেখা যায়", "of Bangla words can now be written in your font")}</span>
            </>
          )}
        </div>
        {props.building && <p className="pencil">{t("আপনার ফন্ট বানাচ্ছি…", "making your font…")}</p>}
        {props.note && <p className="margin-note">{props.note}</p>}
        {word && props.userFont && !props.building ? (
          <>
            <p className="pencil small-note">{t("এখনই আপনার ফন্টে লেখা যায়:", "Your font can already write:")}</p>
            <p className="reward-sample" lang="bn" style={{ fontFamily: font }}>
              {word}
            </p>
          </>
        ) : (
          <>
            <p className="reward-sample" lang={english ? "en" : "bn"} style={{ fontFamily: font }}>
              {chapter.sample}
            </p>
            <p className="pencil small-note">{t("ধূসর ঘর: যে অক্ষর এখনও আঁকা হয়নি।", "Grey boxes: letters not drawn yet.")}</p>
          </>
        )}
        {known && few && !english && (
          <p className="pencil small-note">
            {t(`বাংলা শব্দের ${num(pct(props.words!))}% এখন লেখা যায়।`, `${pct(props.words!)}% of Bangla words can be written now.`)}
          </p>
        )}
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
