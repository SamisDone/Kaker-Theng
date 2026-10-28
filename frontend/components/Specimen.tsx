"use client";

import type { SessionMeta } from "@/lib/api";
import type { Chapter, ChapterId } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import type { LayoutCell } from "@/lib/layout";

// Every glyph on a thin-ruled grid, by chapter. Tap one to draw it again.
// Glyphs not in the font yet: an empty box; a small red mark where a page
// photo was read and that box wasn't. A conjunct drawn in two part cells
// (ম্ম: one box for each half) shows once; tapping it opens the part still
// to draw, or the first.
export function Specimen(props: {
  chapters: Chapter[]; // the chosen font's
  lists: Record<ChapterId, string[]>;
  cells: Map<string, LayoutCell>;
  meta: SessionMeta | null;
  userFont: string | null;
  built: Set<string>; // conjuncts put together from pieces of other letters: grey
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
      {props.chapters.map((c) => (
        <div className="specimen-page" key={c.id}>
          <h3>{t(c.name[0], c.name[1])}</h3>
          <div className="specimen-grid" role="group" aria-label={t(c.name[0], c.name[1])}>
            {byText(props.lists[c.id], props.cells).map((ids) => {
              const cell = props.cells.get(ids[0])!;
              const isOk = (id: string) => Boolean(font) && (status.get(id) ?? "missing") !== "missing";
              const ok = ids.some(isOk);
              const flagged = !ok && ids.some((id) => status.has(id));
              const auto = ok && ids.filter(isOk).every((id) => props.built.has(id));
              return (
                <button
                  key={ids[0]}
                  type="button"
                  className={`glyph${flagged ? " missing" : ""}${auto ? " auto" : ""}`}
                  aria-label={`${cell.text}${ok ? "" : t(", এখনও ফন্টে নেই", ", not in the font yet")}${auto ? t(", টুকরো জুড়ে বানানো", ", put together from pieces") : ""}: ${t("আবার আঁকুন", "draw again")}`}
                  onClick={() => props.onRedraw(ids.find((id) => !isOk(id)) ?? ids[0])}
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

/** Cell ids grouped by the text they draw, in order. */
function byText(ids: string[], cells: Map<string, LayoutCell>): string[][] {
  const groups = new Map<string, string[]>();
  for (const id of ids) {
    const text = cells.get(id)!.text;
    groups.set(text, [...(groups.get(text) ?? []), id]);
  }
  return [...groups.values()];
}
