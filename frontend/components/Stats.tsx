"use client";

import { pct } from "@/lib/bn";
import type { Script } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";

// How far each language of the font has come. Bangla: the share of Bangla
// words it writes. English: letters drawn out of 76, and the share of common
// English words it writes (the 5,000 most used, from wordfreq).
export type LangStat = { drawn: number; total: number; words: number | null }; // words: null until the server has built the font
export type Stats = Partial<Record<Script, LangStat>>;

/** One sentence for one language: what the font writes now. */
export function StatLine({ script, stat, className }: { script: Script; stat: LangStat; className?: string }) {
  const { t, num } = useLang();
  if (script === "bn") {
    return (
      <p className={className}>
        {stat.words === null
          ? t(`বাংলা: ${num(stat.total)}টার মধ্যে ${num(stat.drawn)}টা অক্ষর আঁকা হয়েছে।`, `Bangla: ${stat.drawn} of ${stat.total} letters drawn.`)
          : t(`বাংলা শব্দের ${num(pct(stat.words))}% এখন আপনার ফন্টে লেখা যায়।`, `${pct(stat.words)}% of Bangla words can now be written in your font.`)}
      </p>
    );
  }
  const letters = t(`ইংরেজি: ${num(stat.total)}টার মধ্যে ${num(stat.drawn)}টা অক্ষর`, `English: ${stat.drawn} of ${stat.total} letters`);
  return (
    <p className={className}>
      {stat.words === null
        ? `${letters}${t(" আঁকা হয়েছে।", " drawn.")}`
        : `${letters}${t(`; সাধারণ ইংরেজি শব্দের ${num(pct(stat.words))}% লেখা যায়।`, `; ${pct(stat.words)}% of common English words can be written.`)}`}
    </p>
  );
}
