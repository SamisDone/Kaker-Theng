"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { DrawCanvas, MiniCell } from "@/components/DrawCanvas";
import { bnNum, pct } from "@/lib/bn";
import type { Lang } from "@/lib/drawstore";
import type { Layout, LayoutCell } from "@/lib/layout";
import { signName } from "@/lib/names";
import type { Stroke } from "@/lib/strokes";

const SAMPLE_BN = "আমি বাংলায় লিখি। কাকের ঠ্যাং বকের ঠ্যাং";
const SAMPLE_EN = "The quick brown fox jumps over the lazy dog.";
const NEIGHBOURS = 4;
// Missing letters in the sample show as faint boxes from this font
// (public/kt/missing.woff2), never in another typeface.
const MISSING_FONT = '"KT Missing"';

/** What to draw in this cell, in both languages. */
function hint(cell: LayoutCell): [string, string] {
  if (cell.fragment) return ["শুধু গাঢ় অংশটা, উদাহরণের মতো", "Only the dark part, as in the example"];
  if (cell.ghost) {
    const name = signName(cell.text, cell.ghost);
    if (name) return [`শুধু ${name[0]}`, `Only the ${name[1]}`];
  }
  if (cell.kind === "latin") return /[A-Z0-9]/.test(cell.text) ? ["ওপরের রেখা পর্যন্ত", "Up to the top line"] : ["ডট-রেখা পর্যন্ত", "Up to the dotted line"];
  if (cell.group === "conjunct") return ["পুরো যুক্তবর্ণটা", "The whole conjunct"];
  return ["মাত্রা ওপরের রেখায়", "মাত্রা on the upper line"];
}

export type Progress = { words: number | null; conjuncts: number | null; building: boolean };

export function DrawPad(props: {
  layout: Layout;
  cells: Map<string, LayoutCell>;
  drawn: Record<string, Stroke[]>;
  at: string | null;
  lang: Lang | null;
  fromPaper: Set<string>; // read from a page photo already
  progress: Progress;
  userFont: string | null;
  syncNote: string | null;
  draft: { id: string; strokes: Stroke[] } | null;
  onDraft: (draft: { id: string; strokes: Stroke[] } | null) => void;
  onSave: (id: string, strokes: Stroke[]) => void;
  onAt: (id: string) => void;
  onLang: (lang: Lang) => void;
  onActivity: () => void;
  onPreview: () => void;
}) {
  const { layout, cells, drawn, fromPaper, lang } = props;
  const lists = useMemo(
    () => ({
      bn: layout.draw_order.filter((id) => cells.get(id)!.kind !== "latin"),
      en: layout.draw_order.filter((id) => cells.get(id)!.kind === "latin"),
    }),
    [layout, cells],
  );
  const order = lists[lang ?? "bn"];
  const done = (id: string) => Boolean(drawn[id]?.length) || fromPaper.has(id);
  const firstOpen = order.find((id) => !done(id)) ?? order[0];
  const at = props.at && order.includes(props.at) ? props.at : firstOpen;
  const index = order.indexOf(at);
  const cell = cells.get(at)!;

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

  // The canvas takes the height left on screen under the letter's prompt and
  // above the buttons: on a phone it fills the screen without scrolling.
  const head = useRef<HTMLDivElement>(null);
  const buttons = useRef<HTMLDivElement>(null);
  const [maxHeight, setMaxHeight] = useState(480);
  useLayoutEffect(() => {
    const measure = () => {
      const used = (head.current?.offsetHeight ?? 0) + (buttons.current?.offsetHeight ?? 0) + 24;
      setMaxHeight(Math.max(200, window.innerHeight - used));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [at, lang]);

  const nextOpen = (from: number) => {
    for (let i = from + 1; i < order.length; i++) if (!done(order[i])) return order[i];
    return null;
  };
  const commit = () => changed && props.onSave(at, strokes);
  const goNext = () => {
    commit();
    props.onAt(nextOpen(index) ?? order[Math.min(index + 1, order.length - 1)]);
  };
  const goBack = () => {
    commit();
    if (index > 0) props.onAt(order[index - 1]);
  };
  const skip = () => props.onAt(nextOpen(index) ?? order[Math.min(index + 1, order.length - 1)]);

  // The last letters drawn before this one, then this one, in one frame so
  // they share a scale and a baseline.
  const strip = useMemo(() => {
    const out: string[] = [];
    for (let i = index - 1; i >= 0 && out.length < NEIGHBOURS; i--) if (drawn[order[i]]?.length) out.unshift(order[i]);
    return out;
  }, [index, drawn, order]);
  const stripCells = [...strip.map((id) => ({ id, s: drawn[id] })), { id: at, s: strokes }].map((n) => ({ ...n, cell: cells.get(n.id)! }));
  const above = Math.max(...stripCells.map((n) => n.cell.draw.base));
  const below = Math.max(...stripCells.map((n) => n.cell.draw.h - n.cell.draw.base));

  const total = layout.draw_order.length;
  const count = layout.draw_order.filter(done).length;
  const fragment = cell.fragment ? layout.fragments.find((f) => f.id === cell.id) : undefined;
  const [hBn, hEn] = hint(cell);
  const font = props.userFont ? `"${props.userFont}", ${MISSING_FONT}` : MISSING_FONT;
  const words = props.progress.words;

  const tabs = (
    <div className="draw-tabs" role="tablist" aria-label="ভাষা · language">
      {(["bn", "en"] as const).map((l) => (
        <button key={l} type="button" role="tab" aria-selected={lang === l} className={`tab${lang === l ? " chosen" : ""}`} onClick={() => props.onLang(l)}>
          {l === "bn" ? "বাংলা" : "English"}
          <span className="mono"> {bnNum(lists[l].filter(done).length)}/{bnNum(lists[l].length)}</span>
        </button>
      ))}
    </div>
  );

  if (!lang) {
    return (
      <div className="drawpad" id="drawpad">
        <p>
          কোনটা দিয়ে শুরু করবেন? পরে যেকোনো সময় বদলাতে পারবেন।
          <span className="en-sub" lang="en">
            Start with which? You can switch any time.
          </span>
        </p>
        <p>
          <button type="button" className="button primary" onClick={() => props.onLang("bn")}>
            বাংলা আগে <span className="en">· Bangla first</span>
          </button>
          <button type="button" className="button" onClick={() => props.onLang("en")}>
            ইংরেজি আগে <span className="en">· English first</span>
          </button>
        </p>
      </div>
    );
  }

  return (
    <div className="drawpad" id="drawpad">
      <div className="draw-grid">
        <div className="draw-main">
          <div ref={head}>
            {tabs}
            <div className="draw-status mono" aria-live="polite">
              <span>{words !== null ? `শব্দ ${bnNum(pct(words))}% · words ${pct(words)}%` : props.progress.building ? "ফন্ট বানাচ্ছি… · building…" : "শব্দ — · words —"}</span>
              <span>
                {bnNum(count)}/{bnNum(total)} · {count}/{total} letters
              </span>
            </div>
            <div className="draw-target">
              <span className="draw-letter" lang={cell.kind === "latin" ? "en" : "bn"}>
                {cell.text}
              </span>
              <span className="draw-hint">
                {hBn}
                <span className="en-sub" lang="en">
                  {hEn}
                </span>
              </span>
            </div>
          </div>
          <DrawCanvas
            cell={cell}
            strokes={strokes}
            penMm={layout.pen_mm}
            maxHeight={maxHeight}
            onStroke={(s) => setStrokes((prev) => [...prev, s])}
            onActivity={props.onActivity}
          />
          <div ref={buttons}>
            <div className="draw-buttons">
              <button type="button" className="button" onClick={() => setStrokes((p) => p.slice(0, -1))} disabled={!strokes.length}>
                ফেরান <span className="en">· undo</span>
              </button>
              <button type="button" className="button" onClick={() => setStrokes([])} disabled={!strokes.length}>
                মুছুন <span className="en">· clear</span>
              </button>
              <button type="button" className="button" onClick={props.onPreview} disabled={props.progress.building}>
                দেখুন <span className="en">· preview</span>
              </button>
            </div>
            <div className="draw-buttons">
              <button type="button" className="button" onClick={goBack} disabled={index === 0}>
                আগের <span className="en">· back</span>
              </button>
              <button type="button" className="button" onClick={skip}>
                বাদ <span className="en">· skip</span>
              </button>
              <button type="button" className="button primary" onClick={goNext} disabled={!strokes.length && !drawn[at]?.length}>
                পরের <span className="en">· next</span>
              </button>
            </div>
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
            {stripCells.map((n) => (
              <MiniCell key={n.id} cell={n.cell} strokes={n.s} penMm={layout.pen_mm} above={above} below={below} current={n.id === at} />
            ))}
          </div>
          <p className="en-sub" lang="en">
            Your last letters at one scale: keep them about the same size.
          </p>

          <p className="word-coverage" aria-live="polite">
            {words !== null ? (
              <>
                আপনি এখন বাংলা শব্দের <strong>{bnNum(pct(words))}%</strong> লিখতে পারেন
                <span className="en-sub" lang="en">
                  You can write {pct(words)}% of Bangla words{props.progress.building ? " · updating…" : ""}
                </span>
              </>
            ) : (
              <>
                {props.progress.building ? "ফন্ট বানাচ্ছি…" : "কয়েকটা অক্ষর আঁকলেই হিসেব দেখাবে।"}
                <span className="en-sub" lang="en">
                  {props.progress.building ? "building your font…" : "Draw a few letters to see how much you can write."}
                </span>
              </>
            )}
          </p>
          {props.progress.conjuncts !== null && (
            <p className="en-sub conjunct-line">
              যুক্তবর্ণ {bnNum(pct(props.progress.conjuncts))}% · conjuncts and phalas in real text: {pct(props.progress.conjuncts)}%
            </p>
          )}
          {props.syncNote && <p className="margin-note">{props.syncNote}</p>}
          {props.userFont && (
            <div className="draw-sample" style={{ fontFamily: font }} aria-label="নমুনা · sample in your font so far">
              <p lang="bn">{SAMPLE_BN}</p>
              <p lang="en" style={{ fontFamily: font }}>
                {SAMPLE_EN}
              </p>
              <p className="en-sub" lang="en" style={{ fontFamily: "var(--en)" }}>
                Grey boxes: letters not drawn yet.
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
