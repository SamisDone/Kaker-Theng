"use client";

import { useId, useState } from "react";
import { MISSING_FONT } from "@/components/RewardScreen";
import { useSaver } from "@/components/SaveNote";
import { useLang } from "@/lib/i18n";
import { textImage, textPdf } from "@/lib/khata";

const SAMPLE = "আমি প্রতিদিন সকালে চা খাই। কর্মী ক্ষমা চাইল।\nবিদ্যালয়ের সামনে বৃষ্টি পড়ছে।\nThe quick brown fox jumps over the lazy dog.";

// Lines stay on the khata rules: the line height is a whole number of rules.
const SIZE = 28;
const LINE = Math.ceil((SIZE * 1.45) / 32) * 32;

export function TryIt({ userFont }: { userFont: string | null }) {
  const { t } = useLang();
  const id = useId();
  const [text, setText] = useState(SAMPLE);
  const { save: run, making: saving, note } = useSaver();
  const family = userFont ? `"${userFont}", ${MISSING_FONT}` : null;

  function save(kind: "png" | "pdf") {
    if (!family) return;
    const title = t("আমার হাতের লেখা", "My handwriting");
    void run(kind, async () => ({
      blob: kind === "png" ? await textImage(text, family) : await textPdf(text, family, title),
      name: `kaker-theng.${kind}`,
      title,
    }));
  }

  return (
    <div className="tryit">
      <label htmlFor={id}>{userFont ? t("লিখে দেখুন", "Type to try your font") : t("কয়েকটা অক্ষর আঁকলে এখানে আপনার ফন্ট দেখাবে।", "Your font shows here once you've drawn a few letters.")}</label>
      <textarea
        id={id}
        value={text}
        spellCheck={false}
        onChange={(e) => setText(e.target.value)}
        style={{
          fontFamily: family ?? "var(--bn)",
          fontSize: SIZE,
          lineHeight: `${LINE}px`,
          backgroundSize: `8px ${LINE}px`,
        }}
      />
      {userFont && (
        <p className="save-image">
          <button type="button" className="button" onClick={() => save("png")} disabled={saving !== null}>
            {saving === "png" ? t("বানাচ্ছি…", "making it…") : t("ছবি হিসেবে সেভ করুন", "Save as image")}
          </button>
          <button type="button" className="button" onClick={() => save("pdf")} disabled={saving !== null}>
            {saving === "pdf" ? t("বানাচ্ছি…", "making it…") : t("PDF হিসেবে সেভ করুন", "Save as PDF")}
          </button>
        </p>
      )}
      {userFont && note}
    </div>
  );
}
