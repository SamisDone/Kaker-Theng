"use client";

import { useEffect, useRef, useState } from "react";
import { Download } from "@/components/Download";
import { Icon } from "@/components/Icons";
import { useSaver } from "@/components/SaveNote";
import { Specimen } from "@/components/Specimen";
import { StatLine, type Stats } from "@/components/Stats";
import { TopBar } from "@/components/TopBar";
import { firstText, TryIt } from "@/components/TryIt";
import type { SessionMeta } from "@/lib/api";
import { type Chapter, type ChapterId, type Fonts, type Script, scriptsOf } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import type { LayoutCell } from "@/lib/layout";

// The font so far: type in it and keep that as a picture (the main thing),
// download the font for a computer, see every letter (tap one to redraw it).
// Only the chosen language(s); the other can be added from here.
export function FontScreen(props: {
  session: string | null;
  meta: SessionMeta | null;
  fonts: Fonts;
  chapters: Chapter[]; // the chosen font's
  lists: Record<ChapterId, string[]>;
  cells: Map<string, LayoutCell>;
  stats: Stats;
  written: Script[]; // languages with letters drawn or read from paper
  userFont: string | null;
  building: boolean;
  onBack: () => void;
  onRedraw: (id: string) => void;
  onAdd: (script: Script) => void; // draw the other language too
  strokesFile: () => { blob: Blob; name: string; title: string } | null;
}) {
  const { t } = useLang();
  const scripts = scriptsOf(props.fonts);

  // What the font has: drawn here, or read from a page photo.
  const inFont = new Set(Object.keys(props.meta?.drawn ?? {}));
  for (const p of Object.values(props.meta?.pages ?? {})) for (const c of p.cells) if (c.status !== "missing") inFont.add(c.id);
  const built = new Set(props.meta?.built ?? []);
  const groups = props.chapters.map((c) => ({
    id: c.id,
    name: t(c.name[0], c.name[1]),
    items: props.lists[c.id].filter((id) => inFont.has(id)).map((id) => ({ text: props.cells.get(id)!.text, auto: built.has(id) })),
    note:
      c.id === "conjuncts"
        ? t("ধূসর: আপনার অন্য অক্ষরের টুকরো জুড়ে বানানো। আমার ফন্ট-এ চাপ দিয়ে আবার আঁকা যায়।", "Grey: put together from pieces of your other letters. Tap it under My font to draw it again.")
        : undefined,
  }));

  // The try-it text: sentences (or words) the font already writes, in the
  // chosen language(s), until the visitor types their own.
  const [typed, setTyped] = useState<string | null>(null);
  const first = props.meta?.font ? firstText(props.meta, scripts) : "";
  const text = typed ?? first;

  // Hidden: "export my strokes", for sending a drawing that came out wrong.
  // Shown with ?debug=1, or by holding the heading down for a moment.
  const [debug, setDebug] = useState(false);
  const hold = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => setDebug(new URLSearchParams(location.search).get("debug") === "1"), []);
  const exporter = useSaver();
  const exportStrokes = () => {
    const file = props.strokesFile();
    if (file) void exporter.save("strokes", async () => file);
  };
  const release = () => {
    if (hold.current) clearTimeout(hold.current);
    hold.current = null;
  };
  const other: Script | null = props.fonts === "both" ? null : props.fonts === "bn" ? "en" : "bn";
  return (
    <div className="screen font-screen">
      <TopBar>
        <button type="button" className="link-button" onClick={props.onBack}>
          <Icon name="back" size={18} /> {t("ফিরে যান", "Back")}
        </button>
      </TopBar>
      <h2
        onPointerDown={() => {
          release();
          hold.current = setTimeout(() => setDebug(true), 700);
        }}
        onPointerUp={release}
        onPointerLeave={release}
        onPointerCancel={release}
        onContextMenu={(e) => e.preventDefault()}
        className="font-title"
      >
        {t("আমার ফন্ট", "My font")}
      </h2>
      <div aria-live="polite">
        {props.building ? <p>{t("ফন্ট বানাচ্ছি…", "making your font…")}</p> : scripts.map((s) => <StatLine key={s} script={s} stat={props.stats[s]!} />)}
      </div>
      <TryIt userFont={props.userFont} text={text} onText={setTyped} />
      <Download
        session={props.session}
        ready={Boolean(props.meta?.font)}
        userFont={props.userFont}
        groups={groups}
        text={text}
        sample={first}
        written={props.written}
        bangla={scripts.includes("bn")}
      />
      {other && (
        <p className="add-language">
          <button type="button" className="button" onClick={() => props.onAdd(other)}>
            {other === "en" ? t("ইংরেজিও আঁকুন", "Add English") : t("বাংলাও আঁকুন", "Add Bangla")}
          </button>
        </p>
      )}
      <Specimen chapters={props.chapters} lists={props.lists} cells={props.cells} meta={props.meta} userFont={props.userFont} built={built} onRedraw={props.onRedraw} />
      {debug && (
        <>
          <p>
            <button type="button" className="link-button" onClick={exportStrokes}>
              {t("আমার আঁকা অক্ষরগুলো ফাইলে দিন (JSON)", "Export my strokes (JSON)")}
            </button>
          </p>
          {exporter.note}
        </>
      )}
      <footer className="footer" lang="en">
        Built on Noto Sans Bengali (SIL Open Font License 1.1). Conjunct and word frequencies from Bangla Wikipedia (CC BY-SA 4.0). English word frequencies from wordfreq by Robyn Speer (CC BY-SA 4.0), which includes SUBTLEX by Brysbaert et al.
      </footer>
    </div>
  );
}
