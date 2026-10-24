// The template layout, exported from the backend into public/kt/ by
// backend/scripts/export_frontend_assets.py.

// The drawing canvas for a cell, in mm inside the cell box (origin top-left,
// y down): the same guides and faint ghost letter the template prints.
export type DrawGeometry = {
  w: number;
  h: number;
  base: number; // baseline
  head: number; // মাত্রা / cap line
  xh?: number; // Latin x-height (dashed)
  inset: number; // guide lines stop this far from the border
  ghost: string; // SVG path of the faint ghost letter(s); "" if none
};

export type LayoutCell = {
  id: string;
  text: string;
  ghost: string | null;
  group: string;
  kind: string; // "latin" | "base" | "mark"
  fragment: boolean;
  draw: DrawGeometry;
};

export type Fragment = { id: string; text: string; ghost: string; piece: string; viewBox: number[] };

export type Layout = {
  fingerprint: string;
  template_version: number;
  template_pdf: string; // static copy in /kt/
  headline: number; // মাত্রা height in font units
  pages: Record<string, { title_bn: string; title_en: string; optional: boolean; cells: LayoutCell[] }>;
  fragments: Fragment[];
  coverage_targets: { pages_1_2: number; all_pages: number };
  draw_order: string[]; // every cell id, most useful first
  pen_mm: number; // the drawing pen's width
};

export function cellsById(layout: Layout): Map<string, LayoutCell> {
  const out = new Map<string, LayoutCell>();
  for (const page of Object.values(layout.pages)) for (const c of page.cells) out.set(c.id, c);
  return out;
}

export async function loadLayout(): Promise<Layout> {
  const res = await fetch("/kt/layout.json");
  return res.json();
}
