"use client";

import { useState } from "react";
import type { SessionMeta } from "@/lib/api";
import { bnNum } from "@/lib/bn";
import type { Layout, LayoutCell } from "@/lib/layout";

// Every glyph on a thin-ruled grid. Click one to see it large (inline, no
// popup). Glyphs not in the font yet: an empty box with a small red mark.
export function Specimen({ layout, meta, userFont }: { layout: Layout; meta: SessionMeta | null; userFont: string | null }) {
  const [picked, setPicked] = useState<{ cell: LayoutCell; ok: boolean } | null>(null);
  const status = new Map<string, string>();
  for (const p of Object.values(meta?.pages ?? {})) for (const c of p.cells) status.set(c.id, c.status);
  for (const id of Object.keys(meta?.drawn ?? {})) status.set(id, "ok"); // drawn in the browser
  const font = userFont ? `"${userFont}", var(--bn)` : undefined;

  return (
    <div>
      <div className="glyph-large" aria-live="polite">
        {picked ? (
          <>
            <span className="big" style={{ fontFamily: picked.ok ? font : undefined, color: picked.ok ? undefined : "var(--rule)" }}>
              {picked.cell.text}
            </span>
            <span>
              {picked.ok ? "ফন্টে আছে" : "এখনো নেই"}
              <span className="en-sub" lang="en">
                {picked.ok ? "in your font" : "not in your font yet"} · <span className="mono">{picked.cell.id}</span>
              </span>
            </span>
          </>
        ) : (
          <span>
            একটা অক্ষরে চাপ দিন, বড় করে দেখাবে।
            <span className="en-sub" lang="en">
              Click a glyph to see it large.
            </span>
          </span>
        )}
      </div>
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
                    aria-pressed={picked?.cell.id === cell.id}
                    aria-label={`${cell.text}${ok ? "" : ", not in the font yet"}`}
                    onClick={() => setPicked({ cell, ok })}
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
