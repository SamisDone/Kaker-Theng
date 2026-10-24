"use client";

import { useId, useState } from "react";
import { MISSING_FONT } from "@/components/RewardScreen";
import { useLang } from "@/lib/i18n";
import { saveFile } from "@/lib/savefile";
import { textImage } from "@/lib/textimage";

const SAMPLE = "আমি প্রতিদিন সকালে চা খাই। কর্মী ক্ষমা চাইল।\nবিদ্যালয়ের সামনে বৃষ্টি পড়ছে।\nThe quick brown fox jumps over the lazy dog.";

// Lines stay on the khata rules: the line height is a whole number of rules.
const SIZE = 28;
const LINE = Math.ceil((SIZE * 1.45) / 32) * 32;

export function TryIt({ userFont }: { userFont: string | null }) {
  const { t } = useLang();
  const id = useId();
  const [text, setText] = useState(SAMPLE);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  const family = userFont ? `"${userFont}", ${MISSING_FONT}` : null;

  async function saveImage() {
    if (!family) return;
    setSaving(true);
    setFailed(false);
    try {
      await saveFile(await textImage(text, family), "kaker-theng.png", t("আমার হাতের লেখা", "My handwriting"));
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
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
          <button type="button" className="button" onClick={saveImage} disabled={saving}>
            {saving ? t("ছবি বানাচ্ছি…", "making the image…") : t("ছবি হিসেবে সেভ করুন", "Save as image")}
          </button>
          {failed && <span className="margin-note">{t("ছবিটা বানানো গেল না।", "Couldn't make the image.")}</span>}
        </p>
      )}
    </div>
  );
}
