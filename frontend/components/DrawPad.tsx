"use client";

import { useEffect, useMemo, useState } from "react";
import { DrawCanvas, MiniCell } from "@/components/DrawCanvas";
import { bnNum, pct } from "@/lib/bn";
import type { Layout, LayoutCell } from "@/lib/layout";
import type { Stroke } from "@/lib/strokes";

const SAMPLE_BN = "আমি বাংলায় লিখি। কাকের ঠ্যাং বকের ঠ্যাং";
const SAMPLE_EN = "The quick brown fox jumps over the lazy dog.";
const NEIGHBOURS = 4;
const DOTTED = "◌"; // ◌, what a sign is shown on when it stands alone

/** What to draw in this cell, in both languages. */
function hint(cell: LayoutCell): [string, string] {
  if (cell.fragment)
    return ["শুধু গাঢ় অংশটা আঁকুন, উদাহরণের মতো। হালকা অংশটা ঘরে দেখানো আছে।", "Draw only the dark part, as in the example. The faint part is already in the box."];
  if (cell.ghost) {
    const sign = cell.text.replace(cell.ghost, "");
    const shown = /^[ঀ-৿]/.test(sign) && "ািীুূৃেৈৗঁংঃ়্".includes(sign[0]) ? DOTTED + sign : sign;
    return [`শুধু ${shown} আঁকুন, হালকা ${cell.ghost}-এর সাথে, যেমন লেখেন।`, `Draw only ${shown}, with the faint ${cell.ghost}, the way you write it.`];
  }
  if (cell.kind === "latin")
    return ["রেখার ওপর লিখুন।", /[A-Z0-9]/.test(cell.text) ? "Capitals and digits reach the top line." : "Small letters reach the dashed line; tails go below."];
  if (cell.group === "conjunct") return ["পুরো যুক্তবর্ণটা একসাথে আঁকুন।", "Draw the whole conjunct, as you write it."];
  return ["মাত্রা ওপরের রেখায়, অক্ষর নিচের রেখায়।", "The মাত্রা on the upper line, the letter on the baseline."];
}

export function DrawPad(props: {
  layout: Layout;
  cells: Map<string, LayoutCell>;
  drawn: Record<string, Stroke[]>;
  at: string | null;
  fromPaper: Set<string>; // read from a page photo already
  coverage: number | null;
  building: boolean;
  userFont: string | null;
  syncNote: string | null;
  draft: { id: string; strokes: Stroke[] } | null;
  onDraft: (draft: { id: string; strokes: Stroke[] } | null) => void;
  onSave: (id: string, strokes: Stroke[]) => void;
  onAt: (id: string) => void;
}) {
  const { layout, cells, drawn, fromPaper } = props;
  const order = layout.draw_order;
  const done = (id: string) => Boolean(drawn[id]?.length) || fromPaper.has(id);
  const firstOpen = order.find((id) => !done(id)) ?? order[0];
  const at = props.at && cells.has(props.at) ? props.at : firstOpen;
  const index = order.indexOf(at);
  const cell = cells.get(at)!;

  // The letter on screen: an unfinished draft (kept across a closed tab)
  // wins over what was saved for it.
  const initial = (id: string) => (props.draft?.id === id ? props.draft.strokes : (drawn[id] ?? []));
  const [strokes, setStrokes] = useState<Stroke[]>(() => initial(at));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => setStrokes(initial(at)), [at, drawn]);

  const nextOpen = (from: number) => {
    for (let i = from + 1; i < order.length; i++) if (!done(order[i])) return order[i];
    return null;
  };
  const changed = JSON.stringify(strokes) !== JSON.stringify(drawn[at] ?? []);
  const commit = () => changed && props.onSave(at, strokes);
  // Every stroke is kept in this browser at once, not only on "next".
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => props.onDraft(changed ? { id: at, strokes } : null), [strokes]);

  const goNext = () => {
    commit();
    props.onAt(nextOpen(index) ?? order[Math.min(index + 1, order.length - 1)]);
  };
  const goBack = () => {
    commit();
    if (index > 0) props.onAt(order[index - 1]);
  };
  const skip = () => props.onAt(nextOpen(index) ?? order[Math.min(index + 1, order.length - 1)]);

  // Previously drawn letters, at one small scale, baselines lined up.
  const neighbours = useMemo(() => {
    const out: string[] = [];
    for (let i = index - 1; i >= 0 && out.length < NEIGHBOURS; i--) if (drawn[order[i]]?.length) out.unshift(order[i]);
    return out;
  }, [index, drawn, order]);
  const strip = [...neighbours.map((id) => ({ id, s: drawn[id] })), { id: at, s: strokes }];
  const maxBase = Math.max(...strip.map((n) => cells.get(n.id)!.draw.base));

  const fragment = cell.fragment ? layout.fragments.find((f) => f.id === cell.id) : undefined;
  const total = order.length;
  const count = order.filter(done).length;
  const [hBn, hEn] = hint(cell);
  const font = props.userFont ? `"${props.userFont}", var(--bn)` : undefined;

  return (
    <div className="drawpad">
      <div className="draw-progress" aria-live="polite">
        <span className="mono">
          {bnNum(count)} / {bnNum(total)} · {count} of {total} letters
        </span>
        <span className="draw-bar" aria-hidden="true">
          <span style={{ width: `${(100 * count) / total}%` }} />
        </span>
      </div>

      <div className="draw-grid">
        <div>
          <div className="draw-target">
            <span className="draw-letter" lang={cell.kind === "latin" ? "en" : "bn"}>
              {cell.text}
            </span>
            <span className="mono">
              {index + 1}. {cell.id}
            </span>
          </div>
          <p className="draw-hint">
            {hBn}
            <span className="en-sub" lang="en">
              {hEn}
            </span>
          </p>
          <DrawCanvas cell={cell} strokes={strokes} penMm={layout.pen_mm} onStroke={(s) => setStrokes((prev) => [...prev, s])} />
          <div className="draw-buttons">
            <button type="button" className="button" onClick={() => setStrokes((p) => p.slice(0, -1))} disabled={!strokes.length}>
              ফেরান <span className="en">· undo</span>
            </button>
            <button type="button" className="button" onClick={() => setStrokes([])} disabled={!strokes.length}>
              মুছুন <span className="en">· clear</span>
            </button>
          </div>
          <div className="draw-buttons">
            <button type="button" className="button" onClick={goBack} disabled={index === 0}>
              আগের <span className="en">· back</span>
            </button>
            <button type="button" className="button" onClick={skip}>
              বাদ দিন <span className="en">· skip</span>
            </button>
            <button type="button" className="button primary" onClick={goNext} disabled={!strokes.length && !drawn[at]?.length}>
              পরের <span className="en">· next</span>
            </button>
          </div>
        </div>

        <div className="draw-side">
          {fragment && (
            <figure className="example draw-example">
              <svg viewBox={fragment.viewBox.join(" ")} role="img" aria-label={`উদাহরণ ${fragment.text}. Example for ${fragment.text}: draw only the dark part.`}>
                <line x1={fragment.viewBox[0]} x2={fragment.viewBox[0] + fragment.viewBox[2]} y1={0} y2={0} stroke="var(--rule)" strokeWidth={8} />
                <line x1={fragment.viewBox[0]} x2={fragment.viewBox[0] + fragment.viewBox[2]} y1={-layout.headline} y2={-layout.headline} stroke="var(--rule)" strokeWidth={8} />
                <path d={fragment.ghost} fill="var(--rule)" />
                <path d={fragment.piece} fill="var(--ink)" />
              </svg>
              <figcaption className="label">
                <span lang="bn">{fragment.text}</span>
                <span>উদাহরণ · example</span>
              </figcaption>
            </figure>
          )}

          <div className="neighbours" aria-label="আগের আঁকা অক্ষর · your last letters">
            {strip.map((n) => (
              <MiniCell key={n.id} cell={cells.get(n.id)!} strokes={n.s} penMm={layout.pen_mm} pxPerMm={2.6} offsetMm={maxBase - cells.get(n.id)!.draw.base} />
            ))}
          </div>
          <p className="en-sub" lang="en">
            Your last letters, same scale: keep them about the same size.
          </p>

          <p className="coverage" aria-live="polite">
            {props.coverage !== null ? (
              <>
                বাস্তব বাংলা লেখার <strong>{bnNum(pct(props.coverage))}%</strong>
                <span className="en-sub" lang="en">
                  of real Bangla text covered{props.building ? " · updating…" : ""}
                </span>
              </>
            ) : (
              <>
                {props.building ? "ফন্ট বানাচ্ছি…" : "কয়েকটা অক্ষর আঁকলেই ফন্ট তৈরি হবে।"}
                <span className="en-sub" lang="en">
                  {props.building ? "building your font…" : "Your font appears after the first letters."}
                </span>
              </>
            )}
          </p>
          {props.syncNote && <p className="margin-note">{props.syncNote}</p>}
          {props.userFont && (
            <div className="draw-sample" style={{ fontFamily: font }}>
              <p lang="bn">{SAMPLE_BN}</p>
              <p lang="en" style={{ fontFamily: font }}>
                {SAMPLE_EN}
              </p>
            </div>
          )}
          <p>
            <a href="#download">
              যেকোনো সময় থেমে নামাতে পারেন <span className="en">· stop any time and download</span>
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
