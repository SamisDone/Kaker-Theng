"use client";

import { useState } from "react";
import { TopBar } from "@/components/TopBar";
import type { Fonts } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";

const OPTIONS: { id: Fonts; name: [string, string]; time: [string, string] }[] = [
  { id: "bn", name: ["বাংলা", "Bangla"], time: ["প্রায় ১৫ মিনিট", "about 15 minutes"] },
  { id: "en", name: ["English", "English"], time: ["প্রায় ১০ মিনিট", "about 10 minutes"] },
  { id: "both", name: ["দুটোই", "Both"], time: ["২০–৩০ মিনিট", "20–30 minutes"] },
];

// After "draw" (or "paper"), before anything else: which font to make. Both
// is chosen already; the other language can be added later.
export function ChooseScreen(props: { counts: Record<Fonts, number>; onChoose: (fonts: Fonts) => void }) {
  const { t, num } = useLang();
  const [fonts, setFonts] = useState<Fonts>("both");
  return (
    <div className="screen choose-screen">
      <TopBar />
      <fieldset className="choose">
        <legend>
          <h2>{t("কোন ফন্ট বানাবেন?", "Which font?")}</h2>
        </legend>
        {OPTIONS.map((o) => (
          <label key={o.id} className={`choose-row${fonts === o.id ? " chosen" : ""}`}>
            <input type="radio" name="fonts" value={o.id} checked={fonts === o.id} onChange={() => setFonts(o.id)} />
            <span className="choose-name" lang={o.id === "en" ? "en" : undefined}>
              {t(o.name[0], o.name[1])}
            </span>
            <span className="choose-size">
              {t(`${num(props.counts[o.id])}টা ঘর, ${o.time[0]}`, `${props.counts[o.id]} letters, ${o.time[1]}`)}
            </span>
          </label>
        ))}
      </fieldset>
      <p className="pencil small-note">{t("পরে অন্য ভাষাও যোগ করা যাবে; আঁকা কিছুই হারাবে না।", "You can add the other language later; nothing you draw is lost.")}</p>
      <div className="card-buttons">
        <button type="button" className="button big primary" onClick={() => props.onChoose(fonts)}>
          {t("শুরু করুন →", "Start →")}
        </button>
      </div>
    </div>
  );
}
