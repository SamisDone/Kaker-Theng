// The template layout, exported from the backend into public/kt/ by
// backend/scripts/export_frontend_assets.py.

export type LayoutCell = { id: string; text: string; group: string; kind: string; fragment: boolean };

export type Fragment = { id: string; text: string; ghost: string; piece: string; viewBox: number[] };

export type Layout = {
  fingerprint: string;
  template_version: number;
  template_pdf: string; // static copy in /kt/
  headline: number; // মাত্রা height in font units
  pages: Record<string, { title_bn: string; title_en: string; optional: boolean; cells: LayoutCell[] }>;
  fragments: Fragment[];
  coverage_targets: { pages_1_2: number; all_pages: number };
};

export async function loadLayout(): Promise<Layout> {
  const res = await fetch("/kt/layout.json");
  return res.json();
}
