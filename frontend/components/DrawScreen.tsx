"use client";

import { useEffect, useState } from "react";
import { DrawCanvas } from "@/components/DrawCanvas";
import { Icon } from "@/components/Icons";
import { TopBar } from "@/components/TopBar";
import type { Chapter } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import type { LayoutCell } from "@/lib/layout";
import { signName } from "@/lib/names";
import type { Stroke } from "@/lib/strokes";

/** What to draw in this cell, as [Bangla, English]: one short line. */
function hint(cell: LayoutCell): [string, string] {
  if (cell.fragment) return ["শুধু দাগ-কাটা ঘরের অংশটা", "Only the part in the dashed box"];
  if (cell.ghost) {
    const name = signName(cell.text, cell.ghost);
    if (name) return [`শুধু ${name[0]}, দাগ-কাটা ঘরে`, `Only the ${name[1]}, in the dashed box`];
  }
  if (cell.kind === "latin") {
    if (/[a-z]/.test(cell.text)) return ["ডট-রেখা পর্যন্ত", "Up to the dotted line"];
    if (/[A-Z0-9]/.test(cell.text)) return ["ওপরের রেখা পর্যন্ত", "Up to the top line"];
    return ["নিজের মতো করে", "Your own way"];
  }
  if (cell.group === "conjunct") return ["পুরো যুক্তাক্ষরটা", "The whole conjunct"];
  if (cell.text === "।") return ["ওপরের রেখা থেকে নিচের রেখা", "From the top line to the bottom line"];
  if (cell.draw.matra) return ["মাত্রা ওপরের রেখায়", "The মাত্রা on the top line"];
  return ["নিজের মতো করে লিখুন", "Write it your own way"];
}

// One letter at a time, filling the screen: nothing scrolls, and the screen
// stays put from letter to letter.
export function DrawScreen(props: {
  chapter: Chapter;
  order: string[]; // this chapter's cells, most useful first
  cells: Map<string, LayoutCell>;
  at: string;
  drawn: Record<string, Stroke[]>;
  done: (id: string) => boolean;
  penMm: number;
  draft: { id: string; strokes: Stroke[] } | null;
  syncNote: string | null;
  onDraft: (draft: { id: string; strokes: Stroke[] } | null) => void;
  onSave: (id: string, strokes: Stroke[]) => void;
  onAt: (id: string) => void;
  onChapterEnd: () => void;
  onActivity: () => void;
  onChapters: () => void;
  onFont: () => void;
}) {
  const { t, num } = useLang();
  const { order, at, drawn, done } = props;
  const index = order.indexOf(at);
  const cell = props.cells.get(at)!;

  // The letter on screen: an unfinished draft (kept across a closed tab)
  // wins over what was saved for it.
  const initial = (id: string) => (props.draft?.id === id ? props.draft.strokes : (drawn[id] ?? []));
  const [strokes, setStrokes] = useState<Stroke[]>(() => initial(at));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => setStrokes(initial(at)), [at, drawn]);
  const changed = JSON.stringify(strokes) !== JSON.stringify(drawn[at] ?? []);
  // Every stroke is kept in this browser at once, not only on "next".
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => props.onDraft(changed ? { id: at, strokes } : null), [strokes]);

  const nextOpen = () => {
    for (let i = index + 1; i < order.length; i++) if (!done(order[i])) return order[i];
    return null;
  };
  const commit = () => changed && props.onSave(at, strokes);
  // On to the next letter not drawn yet. In a chapter that is all drawn
  // (back to redraw some), simply the next one. Past the end: the reward.
  const forward = () => {
    const next = nextOpen() ?? (order.every(done) ? order[index + 1] : null);
    if (next) props.onAt(next);
    else props.onChapterEnd();
  };
  const goNext = () => {
    commit();
    forward();
  };
  const goBack = () => {
    commit();
    if (index > 0) props.onAt(order[index - 1]);
  };

  const { chapter } = props;
  const doneCount = order.filter(done).length;
  const [hBn, hEn] = hint(cell);

  return (
    <div className="screen draw-screen">
      <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={order.length} aria-valuenow={doneCount} aria-label={t("এই অধ্যায়ে আঁকা হয়েছে", "Drawn in this chapter")}>
        <span style={{ width: `${(100 * doneCount) / order.length}%` }} />
      </div>
      <TopBar onFont={props.onFont} home={false}>
        <button type="button" className="chapter-button" onClick={props.onChapters} aria-label={t(`${chapter.name[0]}, অধ্যায় বদলান`, `${chapter.name[1]}, change chapter`)}>
          <span className="chapter-name">{t(chapter.name[0], chapter.name[1])}</span>
          <span className="mono count">
            {num(index + 1)}/{num(order.length)}
          </span>
          <Icon name="down" size={16} />
        </button>
      </TopBar>

      <div className="draw-target">
        <span className="draw-letter" lang={cell.kind === "latin" ? "en" : "bn"}>
          {cell.text}
        </span>
        <span className="draw-hint">{t(hBn, hEn)}</span>
      </div>

      <DrawCanvas cell={cell} strokes={strokes} penMm={props.penMm} onStroke={(s) => setStrokes((prev) => [...prev, s])} onActivity={props.onActivity} />

      {props.syncNote && <p className="margin-note sync-note">{props.syncNote}</p>}

      <div className="draw-actions">
        <button type="button" className="icon-button" onClick={goBack} disabled={index === 0} aria-label={t("আগের অক্ষর", "Previous letter")}>
          <Icon name="back" />
          <span aria-hidden="true">{t("আগের", "Back")}</span>
        </button>
        <button type="button" className="icon-button" onClick={forward} aria-label={t("বাদ দিন", "Skip")}>
          <Icon name="skip" />
          <span aria-hidden="true">{t("বাদ", "Skip")}</span>
        </button>
        <button type="button" className="icon-button" onClick={() => setStrokes([])} disabled={!strokes.length} aria-label={t("সব মুছুন", "Clear")}>
          <Icon name="erase" />
          <span aria-hidden="true">{t("মুছুন", "Clear")}</span>
        </button>
        <button type="button" className="icon-button undo" onClick={() => setStrokes((p) => p.slice(0, -1))} disabled={!strokes.length} aria-label={t("ফেরান", "Undo")}>
          <Icon name="undo" />
          <span aria-hidden="true">{t("ফেরান", "Undo")}</span>
        </button>
        <button type="button" className="button primary next" onClick={goNext} disabled={!strokes.length && !drawn[at]?.length}>
          {t("পরের →", "Next →")}
        </button>
      </div>
    </div>
  );
}
