"use client";

import type { SessionMeta } from "@/lib/api";
import { bnNum } from "@/lib/bn";
import type { Layout } from "@/lib/layout";

// Every glyph on a thin-ruled grid. Tap one to redraw it on the canvas.
// Glyphs not in the font yet: an empty box with a small red mark.
export function Specimen({ layout, meta, userFont, onRedraw }: { layout: Layout; meta: SessionMeta | null; userFont: string | null; onRedraw: (id: string) => void }) {
  const status = new Map<string, string>();
  for (const p of Object.values(meta?.pages ?? {})) for (const c of p.cells) status.set(c.id, c.status);
  for (const id of Object.keys(meta?.drawn ?? {})) status.set(id, "ok"); // drawn in the browser
  const font = userFont ? `"${userFont}", var(--bn)` : undefined;

  return (
    <div>
      <p>
        যেকোনো অক্ষরে চাপ দিন: আঁকার ঘরে খুলবে, আবার আঁকতে পারবেন।
        <span className="en-sub" lang="en">
          Tap any letter to open it on the canvas and draw it again.
        </span>
      </p>
      {[1, 2, 3].map((n) => {
        const page = layout.pages[n];
        return (
          <div className="specimen-page" key={n}>
            <h3 className="mono">
              p{n} · {page.title_en}
            </h3>
            <div className="specimen-grid" role="group" aria-label={`পাতা ${bnNum(n)}, page ${n}`}>
              {page.cells.map((cell) => {
                const ok = Boolean(font) && (status.get(cell.id) ?? "missing") !== "missing";
                // A red mark only where a page was read and this cell wasn't.
                const flagged = !ok && status.has(cell.id);
                return (
                  <button
                    key={cell.id}
                    type="button"
                    className={`glyph${flagged ? " missing" : ""}`}
                    aria-label={`${cell.text}${ok ? "" : ", not in the font yet"}: আবার আঁকুন, draw again`}
                    onClick={() => onRedraw(cell.id)}
                    style={{ fontFamily: font }}
                  >
                    {ok ? cell.text : ""}
                    <span className="tiny" aria-hidden="true">
                      {cell.text}
                      {cell.fragment ? "*" : ""}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
