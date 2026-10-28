"use client";

import { useId } from "react";
import { MISSING_FONT } from "@/components/RewardScreen";
import { useSaver } from "@/components/SaveNote";
import type { SessionMeta } from "@/lib/api";
import type { Script } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import { textImage } from "@/lib/khata";

// Lines stay on the khata rules: the line height is a whole number of rules.
const SIZE = 28;
const LINE = Math.ceil((SIZE * 1.45) / 32) * 32;

/** A first text to try, in each language of the font: everyday sentences
 * it writes fully, or, while it writes none, the common words it does.
 * Four lines in all: two of each when it has both. */
export function firstText(meta: SessionMeta, scripts: Script[]): string {
  const n = scripts.length > 1 ? 2 : 4;
  const part = (sentences: string[], words: string[]) => (sentences.length ? sentences.slice(0, n).join("\n") : wordsText(words, n));
  const parts = scripts.map((s) => (s === "bn" ? part(meta.sentences ?? [], meta.words ?? []) : part(meta.en_sentences ?? [], meta.en_words ?? [])));
  return parts.filter(Boolean).join("\n");
}

/** Common words the font already writes, five to a line, at most two
 * lines (and no more than `lines`); words of three letters or more first
 * (not just এই, এর). */
function wordsText(words: string[], lines = 2): string {
  const picked = [...words.filter((w) => w.length > 2), ...words.filter((w) => w.length <= 2)].slice(0, 5 * Math.min(lines, 2));
  const out: string[] = [];
  for (let i = 0; i < picked.length; i += 5) out.push(picked.slice(i, i + 5).join(" "));
  return out.join("\n");
}

// Type in your font, and keep it as a picture: the main thing My font does.
export function TryIt({ userFont, text, onText }: { userFont: string | null; text: string; onText: (text: string) => void }) {
  const { t } = useLang();
  const id = useId();
  const { save, show, making, note } = useSaver();
  const family = userFont ? `"${userFont}", ${MISSING_FONT}` : null;

  const image = () => {
    const title = t("আমার হাতের লেখা", "My handwriting");
    return async () => ({ blob: await textImage(text, family!, t("কাকের ঠ্যাং", "Kaker Theng")), name: "kaker-theng.png", title });
  };

  return (
    <div className="tryit">
      <label htmlFor={id}>{userFont ? t("লিখে দেখুন", "Type to try your font") : t("কয়েকটা অক্ষর আঁকলে এখানে আপনার ফন্ট দেখাবে।", "Your font shows here once you've drawn a few letters.")}</label>
      <textarea
        id={id}
        value={text}
        spellCheck={false}
        placeholder={t("এখানে লিখে দেখুন…", "Type here…")}
        onChange={(e) => onText(e.target.value)}
        style={{
          fontFamily: family ?? "var(--bn)",
          fontSize: SIZE,
          lineHeight: `${LINE}px`,
          backgroundSize: `8px ${LINE}px`,
        }}
      />
      {userFont && (
        <>
          <p className="save-image">
            <button type="button" className="button big primary" onClick={() => family && void save("png", image())} disabled={making !== null || !text.trim()}>
              {making === "png" ? t("বানাচ্ছি…", "making it…") : t("ছবি হিসেবে সেভ / শেয়ার", "Save / share as image")}
            </button>
            <button type="button" className="button big" onClick={() => family && void show("png-show", image())} disabled={making !== null || !text.trim()}>
              {making === "png-show" ? t("বানাচ্ছি…", "making it…") : t("স্ক্রিনে দেখান", "Show on screen")}
            </button>
          </p>
          {note}
        </>
      )}
    </div>
  );
}
