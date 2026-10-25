"use client";

import { useId } from "react";
import { MISSING_FONT } from "@/components/RewardScreen";
import { useSaver } from "@/components/SaveNote";
import { useLang } from "@/lib/i18n";
import { textImage } from "@/lib/khata";

// Lines stay on the khata rules: the line height is a whole number of rules.
const SIZE = 28;
const LINE = Math.ceil((SIZE * 1.45) / 32) * 32;

/** A first text to try: everyday sentences the font writes fully, or,
 * while it writes none, the common words it does. */
export function firstText(sentences: string[], words: string[]): string {
  return sentences.length ? sentences.slice(0, 4).join("\n") : wordsText(words);
}

/** Common words the font already writes, five to a line; words of three
 * letters or more first (not just এই, এর). */
function wordsText(words: string[]): string {
  const picked = [...words.filter((w) => w.length > 2), ...words.filter((w) => w.length <= 2)].slice(0, 10);
  const lines: string[] = [];
  for (let i = 0; i < picked.length; i += 5) lines.push(picked.slice(i, i + 5).join(" "));
  return lines.join("\n");
}

// Type in your font, and keep it as a picture: the main thing My font does.
export function TryIt({ userFont, text, onText }: { userFont: string | null; text: string; onText: (text: string) => void }) {
  const { t } = useLang();
  const id = useId();
  const { save, show, making, note } = useSaver();
  const family = userFont ? `"${userFont}", ${MISSING_FONT}` : null;

  const image = () => {
    const title = t("আমার হাতের লেখা", "My handwriting");
    return async () => ({ blob: await textImage(text, family!), name: "kaker-theng.png", title });
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
