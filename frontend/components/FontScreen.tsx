"use client";

import { useEffect, useRef, useState } from "react";
import { Download } from "@/components/Download";
import { Icon } from "@/components/Icons";
import { Specimen } from "@/components/Specimen";
import { TopBar } from "@/components/TopBar";
import { TryIt } from "@/components/TryIt";
import type { SessionMeta } from "@/lib/api";
import { pct } from "@/lib/bn";
import { CHAPTERS, type ChapterId } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import type { LayoutCell } from "@/lib/layout";

// The font so far: type in it, see every letter (tap one to redraw it),
// download it.
export function FontScreen(props: {
  session: string | null;
  meta: SessionMeta | null;
  lists: Record<ChapterId, string[]>;
  cells: Map<string, LayoutCell>;
  userFont: string | null;
  building: boolean;
  onBack: () => void;
  onRedraw: (id: string) => void;
  onExport: () => Promise<void>;
}) {
  const { t, num } = useLang();
  const words = props.meta?.font ? (props.meta.word_coverage ?? 0) : null;

  // What the font has: drawn here, or read from a page photo.
  const inFont = new Set(Object.keys(props.meta?.drawn ?? {}));
  for (const p of Object.values(props.meta?.pages ?? {})) for (const c of p.cells) if (c.status !== "missing") inFont.add(c.id);
  const groups = CHAPTERS.map((c) => ({ name: t(c.name[0], c.name[1]), texts: props.lists[c.id].filter((id) => inFont.has(id)).map((id) => props.cells.get(id)!.text) }));

  // Hidden: "export my strokes", for sending a drawing that came out wrong.
  // Shown with ?debug=1, or by holding the heading down for a moment.
  const [debug, setDebug] = useState(false);
  const hold = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => setDebug(new URLSearchParams(location.search).get("debug") === "1"), []);
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
      <TryIt userFont={props.userFont} />
      <Download session={props.session} ready={Boolean(props.meta?.font)} userFont={props.userFont} groups={groups} />
      <Specimen lists={props.lists} cells={props.cells} meta={props.meta} userFont={props.userFont} onRedraw={props.onRedraw} />
      {debug && (
        <p>
          <button type="button" className="link-button" onClick={() => void props.onExport()}>
            {t("আমার আঁকা অক্ষরগুলো ফাইলে দিন (JSON)", "Export my strokes (JSON)")}
          </button>
        </p>
      )}
      <footer className="footer" lang="en">
        Built on Noto Sans Bengali (SIL Open Font License 1.1). Conjunct and word frequencies from Bangla Wikipedia (CC BY-SA 4.0).
      </footer>
    </div>
  );
}
