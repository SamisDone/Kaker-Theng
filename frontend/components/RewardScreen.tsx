"use client";

import { StatLine, type Stats } from "@/components/Stats";
import { TopBar } from "@/components/TopBar";
import { pct } from "@/lib/bn";
import { type Chapter, type Script, scriptOf } from "@/lib/chapters";
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
// can write now: big, the number for this chapter's language; under it the
// other language's, when the font has both.
export function RewardScreen(props: {
  chapter: Chapter;
  next: Chapter | null; // the next chapter with letters left
  drawn: number;
  total: number;
  stats: Stats; // each language of the chosen font
  writable: string[]; // common Bangla words the font writes, most common first
  englishSample: string | null; // an English sentence (or word) the font writes
  building: boolean;
  userFont: string | null;
  note: string | null;
  onContinue: () => void;
  onSkipped: () => void; // draw the ones skipped in this chapter
  onFont: () => void;
}) {
  const { t, num } = useLang();
  const { chapter, next, drawn, total, stats } = props;
  const script = scriptOf(chapter.id);
  const english = script === "en";
  const font = props.userFont ? `"${props.userFont}", ${MISSING_FONT}` : MISSING_FONT;
  const left = total - drawn;
  const shown = english ? props.englishSample : showWord(props.writable);
  const stat = stats[script]!;
  const known = stat.words !== null && !props.building;
  const few = !known || stat.words! < WORDS_MEANINGFUL;
  const others = (Object.keys(stats) as Script[]).filter((s) => s !== script);
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
          {english || few ? (
            <>
              <strong>
                {num(stat.drawn)}
                <span className="reward-of">/{num(stat.total)}</span>
              </strong>
              <span>{english ? t("ইংরেজি অক্ষর আঁকা হয়েছে", "English letters drawn") : t("বাংলা অক্ষর আঁকা হয়েছে", "Bangla letters drawn")}</span>
            </>
          ) : (
            <>
              <strong>{num(pct(stat.words!))}%</strong>
              <span>{t("বাংলা শব্দ এখন আপনার ফন্টে লেখা যায়", "of Bangla words can now be written in your font")}</span>
            </>
          )}
        </div>
        {known && (english || few) && (
          <p className={english ? undefined : "pencil small-note"}>
            {english
              ? t(`সাধারণ ইংরেজি শব্দের ${num(pct(stat.words!))}% এখন আপনার ফন্টে লেখা যায়।`, `${pct(stat.words!)}% of common English words can now be written in your font.`)
              : t(`বাংলা শব্দের ${num(pct(stat.words!))}% এখন লেখা যায়।`, `${pct(stat.words!)}% of Bangla words can be written now.`)}
          </p>
        )}
        {!props.building && others.map((s) => <StatLine key={s} script={s} stat={stats[s]!} className="also pencil" />)}
        {props.building && <p className="pencil">{t("আপনার ফন্ট বানাচ্ছি…", "making your font…")}</p>}
        {props.note && <p className="margin-note">{props.note}</p>}
        {shown && props.userFont && !props.building ? (
          <>
            <p className="pencil small-note">{t("এখনই আপনার ফন্টে লেখা যায়:", "Your font can already write:")}</p>
            <p className="reward-sample" lang={english ? "en" : "bn"} style={{ fontFamily: font }}>
              {shown}
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
