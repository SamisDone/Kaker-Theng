"use client";

import { useEffect, useRef, useState } from "react";
import { Download } from "@/components/Download";
import { Icon } from "@/components/Icons";
import { useSaver } from "@/components/SaveNote";
import { Specimen } from "@/components/Specimen";
import { TopBar } from "@/components/TopBar";
import { firstText, TryIt } from "@/components/TryIt";
import type { SessionMeta } from "@/lib/api";
import { pct } from "@/lib/bn";
import { CHAPTERS, type ChapterId } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import type { LayoutCell } from "@/lib/layout";

// The font so far: type in it and keep that as a picture (the main thing),
// download the font for a computer, see every letter (tap one to redraw it).
export function FontScreen(props: {
  session: string | null;
  meta: SessionMeta | null;
  lists: Record<ChapterId, string[]>;
  cells: Map<string, LayoutCell>;
  userFont: string | null;
  building: boolean;
  onBack: () => void;
  onRedraw: (id: string) => void;
  strokesFile: () => { blob: Blob; name: string; title: string } | null;
}) {
  const { t, num } = useLang();
  const words = props.meta?.font ? (props.meta.word_coverage ?? 0) : null;

  // What the font has: drawn here, or read from a page photo.
  const inFont = new Set(Object.keys(props.meta?.drawn ?? {}));
  for (const p of Object.values(props.meta?.pages ?? {})) for (const c of p.cells) if (c.status !== "missing") inFont.add(c.id);
  const built = new Set(props.meta?.built ?? []);
  const groups = CHAPTERS.map((c) => ({
    id: c.id,
    name: t(c.name[0], c.name[1]),
    items: props.lists[c.id].filter((id) => inFont.has(id)).map((id) => ({ text: props.cells.get(id)!.text, auto: built.has(id) })),
    note:
      c.id === "conjuncts"
        ? t("ধূসর: আপনার অন্য অক্ষরের টুকরো জুড়ে বানানো। আমার ফন্ট-এ চাপ দিয়ে আবার আঁকা যায়।", "Grey: put together from pieces of your other letters. Tap it under My font to draw it again.")
        : undefined,
  }));

  // The try-it text: sentences (or words) the font already writes, until
  // the visitor types their own.
  const [typed, setTyped] = useState<string | null>(null);
  const first = props.meta?.font ? firstText(props.meta.sentences ?? [], props.meta.words ?? []) : "";
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
      <p aria-live="polite">
        {props.building
          ? t("ফন্ট বানাচ্ছি…", "making your font…")
          : words !== null
            ? t(`বাংলা শব্দের ${num(pct(words))}% এখন আপনার ফন্টে লেখা যায়।`, `${pct(words)}% of Bangla words can now be written in your font.`)
            : null}
      </p>
      <TryIt userFont={props.userFont} text={text} onText={setTyped} />
      <Download session={props.session} ready={Boolean(props.meta?.font)} userFont={props.userFont} groups={groups} text={text} sample={first} />
      <Specimen lists={props.lists} cells={props.cells} meta={props.meta} userFont={props.userFont} built={built} onRedraw={props.onRedraw} />
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
        Built on Noto Sans Bengali (SIL Open Font License 1.1). Conjunct and word frequencies from Bangla Wikipedia (CC BY-SA 4.0).
      </footer>
    </div>
  );
}
