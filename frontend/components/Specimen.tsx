"use client";

import type { SessionMeta } from "@/lib/api";
import { CHAPTERS, type ChapterId } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import type { LayoutCell } from "@/lib/layout";

// Every glyph on a thin-ruled grid, by chapter. Tap one to draw it again.
// Glyphs not in the font yet: an empty box; a small red mark where a page
// photo was read and that box wasn't.
export function Specimen(props: {
  lists: Record<ChapterId, string[]>;
  cells: Map<string, LayoutCell>;
  meta: SessionMeta | null;
  userFont: string | null;
  onRedraw: (id: string) => void;
}) {
  const { t } = useLang();
  const status = new Map<string, string>();
  for (const p of Object.values(props.meta?.pages ?? {})) for (const c of p.cells) status.set(c.id, c.status);
  for (const id of Object.keys(props.meta?.drawn ?? {})) status.set(id, "ok"); // drawn in the browser
  const font = props.userFont ? `"${props.userFont}", var(--bn)` : undefined;

  return (
    <div className="specimen">
      <p>{t("কোনো অক্ষরে চাপ দিলে সেটা আবার আঁকতে পারবেন।", "Tap a letter to draw it again.")}</p>
      {CHAPTERS.map((c) => (
        <div className="specimen-page" key={c.id}>
          <h3>{t(c.name[0], c.name[1])}</h3>
          <div className="specimen-grid" role="group" aria-label={t(c.name[0], c.name[1])}>
            {props.lists[c.id].map((id) => {
              const cell = props.cells.get(id)!;
              const ok = Boolean(font) && (status.get(id) ?? "missing") !== "missing";
              const flagged = !ok && status.has(id);
              return (
                <button
                  key={id}
                  type="button"
                  className={`glyph${flagged ? " missing" : ""}`}
                  aria-label={`${cell.text}${ok ? "" : t(", এখনও ফন্টে নেই", ", not in the font yet")}: ${t("আবার আঁকুন", "draw again")}`}
                  onClick={() => props.onRedraw(id)}
                  style={{ fontFamily: font }}
                >
                  {ok ? cell.text : ""}
                  <span className="tiny" aria-hidden="true">
                    {cell.text}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
