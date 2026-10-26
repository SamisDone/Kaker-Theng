// Things to look at and share, drawn by the browser on khata paper: the
// try-it text, and the font sheet (every letter in the visitor's font).
// The same layout gives one tall picture sized for a phone, or A4 pages
// for a PDF. The canvas shapes Bangla as the page does.

import { a4Canvas, type PdfPage, pageJpeg, pagesToPdf } from "@/lib/pdf";
import { SaveError } from "@/lib/savefile";

const PHONE_W = 1080; // px; everything below is in these units, scaled for A4
const LINE = 96; // rule spacing
const MARGIN_X = 96; // the red margin line
const LEFT = 132;
const RIGHT = 64;
const TOP = 96;
const BOTTOM = 96;
const TEXT = 56; // try-it text size
const COLS = 8; // font sheet grid
// A phone gives up on a big canvas (toBlob gives nothing): the picture's
// longer side is kept to 4096 px (old phones' GPU limit) and 8 Mpx, then
// tried again at 2048 if that still fails. A4 pages: 200 dpi, then 150.
const PICTURE_SIDES = [4096, 2048];
const PICTURE_AREA = 8_000_000;
const PDF_DPI = [200, 150];

/** What the last picture or PDF took, for the "copy error details" report. */
export const drawLog = { step: "", canvases: [] as string[], font: "", fonts: [] as string[], requests: [] as string[] };
export function resetDrawLog() {
  Object.assign(drawLog, { step: "", canvases: [], font: "", fonts: [], requests: [] });
}

const errText = (err: unknown) => (err instanceof Error ? `${err.name}: ${err.message}` : String(err));

/** The files of the @font-face rules whose fonts failed to load, each fetched again for its HTTP status. */
async function failedFontRequests(): Promise<string[]> {
  const failed = new Set([...document.fonts].filter((f) => f.status === "error").map((f) => f.family.replace(/["']/g, "").trim()));
  const urls = new Set<string>();
  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList;
    try {
      rules = sheet.cssRules;
    } catch {
      continue; // another origin's stylesheet
    }
    for (const rule of Array.from(rules)) {
      if (!(rule instanceof CSSFontFaceRule)) continue;
      if (!failed.has(rule.style.getPropertyValue("font-family").replace(/["']/g, "").trim())) continue;
      for (const m of rule.style.getPropertyValue("src").matchAll(/url\(["']?([^"')]+)/g)) urls.add(new URL(m[1], sheet.href ?? location.href).href);
    }
  }
  return Promise.all(
    [...urls].slice(0, 12).map((u) =>
      fetch(u, { cache: "no-store" }).then(
        (r) => `${u} HTTP ${r.status}`,
        (e) => `${u} ${errText(e)}`,
      ),
    ),
  );
}

const PAPER = "#f4f0e6";
const RULE = "#b9c6e0";
const MARGIN = "#c2412d";
const INK = "#1d2140";
const PENCIL = "#6e685d";
const GREY = "#8a847a"; // a letter put together from pieces, not drawn: lighter than pencil, 3.3:1 on paper

export type SheetItem = { text: string; auto?: boolean }; // auto: put together from pieces of other letters, not drawn as it is

export type Sheet = {
  title: string; // the font's name
  subtitle: string; // "made with Kaker Theng", in the screen's language
  sample: string; // a line in the font
  groups: { id: string; name: string; items: SheetItem[]; note?: string }[]; // chapters, with what was drawn
};

// A block of the page: its height, and how to draw it with its top at y.
// A heading keeps to the page of the block after it.
type Block = { h: number; draw: (ctx: CanvasRenderingContext2D, y: number) => void; keepWithNext?: boolean };

/** The site's own Tiro Bangla (next/font names it), for headings and labels. */
function uiFont(): string {
  return getComputedStyle(document.documentElement).getPropertyValue("--font-tiro-bangla").trim() || "serif";
}

function wrap(ctx: CanvasRenderingContext2D, text: string, width: number): string[] {
  const out: string[] = [];
  for (const para of text.split("\n")) {
    let line = "";
    for (const word of para.split(/\s+/).filter(Boolean)) {
      const next = line ? `${line} ${word}` : word;
      if (line && ctx.measureText(next).width > width) {
        out.push(line);
        line = word;
      } else line = next;
    }
    out.push(line);
  }
  return out;
}

function paper(ctx: CanvasRenderingContext2D, w: number, h: number, s: number) {
  ctx.fillStyle = PAPER;
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = RULE;
  for (let y = (TOP + LINE) * s; y < h; y += LINE * s) ctx.fillRect(0, y - s, w, 2 * s);
  ctx.fillStyle = MARGIN;
  ctx.fillRect(MARGIN_X * s, 0, 3 * s, h);
}

/** Lines of text sitting on the rules. */
function textBlocks(ctx: CanvasRenderingContext2D, text: string, font: string, s: number, width: number): Block[] {
  ctx.font = font;
  return wrap(ctx, text.trim() || " ", width).map((line) => ({
    h: LINE * s,
    draw: (c, y) => {
      c.font = font;
      c.fillStyle = INK;
      c.fillText(line, LEFT * s, y + (LINE - 18) * s);
    },
  }));
}

function sheetBlocks(ctx: CanvasRenderingContext2D, sheet: Sheet, family: string, s: number, width: number): Block[] {
  const ui = uiFont();
  const blocks: Block[] = [
    {
      h: LINE * 2 * s, // two rules: the name on one, "made with" on the next
      draw: (c, y) => {
        c.fillStyle = INK;
        c.font = `${48 * s}px ${ui}`;
        c.fillText(sheet.title, LEFT * s, y + (LINE - 18) * s);
        c.fillStyle = PENCIL;
        c.font = `${24 * s}px ${ui}`;
        c.fillText(sheet.subtitle, LEFT * s, y + (2 * LINE - 18) * s);
      },
    },
    ...textBlocks(ctx, sheet.sample, `${64 * s}px ${family}`, s, width),
  ];
  const cell = width / COLS;
  for (const group of sheet.groups) {
    // A conjunct with two part cells shows once; drawn if either part was.
    const seen = new Map<string, SheetItem>();
    for (const it of group.items) seen.set(it.text, { text: it.text, auto: (seen.get(it.text)?.auto ?? true) && Boolean(it.auto) });
    const items = [...seen.values()];
    if (!items.length) continue;
    const note = items.some((it) => it.auto) ? group.note : undefined;
    blocks.push({
      keepWithNext: true,
      h: (note ? LINE * 1.15 : LINE * 0.75) * s,
      draw: (c, y) => {
        c.fillStyle = PENCIL;
        c.font = `${26 * s}px ${ui}`;
        c.fillText(group.name, LEFT * s, y + 60 * s);
        if (note) {
          c.font = `${18 * s}px ${ui}`;
          c.fillText(note, LEFT * s, y + 96 * s);
        }
      },
    });
    for (let i = 0; i < items.length; i += COLS) {
      const row = items.slice(i, i + COLS);
      blocks.push({
        h: cell + 8 * s,
        draw: (c, y) => {
          row.forEach(({ text, auto }, j) => {
            const x = LEFT * s + j * cell;
            c.fillStyle = PAPER;
            c.fillRect(x, y, cell, cell);
            // Put together, not drawn: grey, in a dashed box like the canvas's "draw here".
            c.strokeStyle = auto ? PENCIL : RULE;
            c.lineWidth = 1.5 * s;
            c.setLineDash(auto ? [6 * s, 5 * s] : []);
            c.strokeRect(x + 0.75 * s, y + 0.75 * s, cell - 1.5 * s, cell - 1.5 * s);
            c.setLineDash([]);
            // The letter in the visitor's font, as large as fits.
            let size = cell * 0.52;
            c.font = `${size}px ${family}`;
            const w = c.measureText(text).width;
            if (w > cell * 0.82) size *= (cell * 0.82) / w;
            c.font = `${size}px ${family}`;
            c.fillStyle = auto ? GREY : INK;
            c.textAlign = "center";
            c.fillText(text, x + cell / 2, y + cell * 0.66);
            // Which letter it is, small, in the site's typeface.
            c.font = `${15 * s}px ${ui}`;
            c.fillStyle = PENCIL;
            c.textAlign = "left";
            c.fillText(text, x + 6 * s, y + cell - 8 * s);
          });
        },
      });
    }
  }
  return blocks;
}

function context(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new SaveError("canvas", `no 2d context for ${canvas.width}x${canvas.height}`);
  return ctx;
}

/** `make` at each size in turn, smaller only when the canvas failed. */
async function smaller<T>(sizes: number[], make: (size: number) => Promise<T>): Promise<T> {
  for (let i = 0; ; i++) {
    try {
      return await make(sizes[i]);
    } catch (err) {
      if (!(err instanceof SaveError && err.code === "canvas") || i === sizes.length - 1) throw err;
    }
  }
}

type Make = (ctx: CanvasRenderingContext2D, s: number, width: number) => Block[];

/** One tall picture for a phone, scaled down to fit `side`. */
async function picture(make: Make, side: number): Promise<Blob> {
  const probe = context(document.createElement("canvas"));
  const full = TOP + make(probe, 1, PHONE_W - LEFT - RIGHT).reduce((a, b) => a + b.h, 0) + BOTTOM;
  const s = Math.min(1, side / Math.max(PHONE_W, full), Math.sqrt(PICTURE_AREA / (PHONE_W * full)));
  const blocks = make(probe, s, (PHONE_W - LEFT - RIGHT) * s);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(PHONE_W * s);
  canvas.height = Math.round((TOP + BOTTOM) * s + blocks.reduce((a, b) => a + b.h, 0));
  const ctx = context(canvas);
  paper(ctx, canvas.width, canvas.height, s);
  let y = TOP * s;
  for (const b of blocks) {
    b.draw(ctx, y);
    y += b.h;
  }
  drawLog.step = "canvas";
  const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/png"));
  const { width, height } = canvas;
  canvas.width = canvas.height = 0; // let the memory go now, not at the next garbage collection
  drawLog.canvases.push(`${width}x${height} ${blob ? "ok" : "failed"}`);
  if (!blob) throw new SaveError("canvas", `toBlob gave nothing for ${width}x${height}`);
  return blob;
}

// The try-it text as a card to share: square, or 4:5 portrait when the text
// needs more room (the shapes chat apps and feeds show whole), the text as
// large as fits, centred on khata rules, the site's name small at the foot.
// Text too long for either at a readable size makes a taller card.
const CARD_W = 1080;
const CARD_HEIGHTS = [1080, 1350];
const CARD_TEXT = [140, 60]; // px: largest, and smallest before the card grows taller
const CARD_FOOT = 120; // the name's band at the bottom
const CREDIT = 30;

/** The largest text size (and its lines) that fits `room` across and down. */
function fitText(ctx: CanvasRenderingContext2D, text: string, family: string, room: [number, number]) {
  for (let size = CARD_TEXT[0]; size >= CARD_TEXT[1]; size -= 4) {
    ctx.font = `${size}px ${family}`;
    const lines = wrap(ctx, text, room[0]);
    const lh = Math.round(size * 1.6);
    if (lines.length * lh <= room[1] && lines.every((l) => ctx.measureText(l).width <= room[0])) return { size, lines, lh };
  }
  return null;
}

async function card(text: string, family: string, credit: string, side: number): Promise<Blob> {
  const probe = context(document.createElement("canvas"));
  const across = CARD_W - LEFT - RIGHT;
  const room = (h: number): [number, number] => [across, h - TOP - CARD_FOOT];
  const [square, tall] = CARD_HEIGHTS.map((h) => fitText(probe, text, family, room(h)));
  // Square unless the portrait card gives clearly larger text.
  let fit = square && (!tall || tall.size < square.size * 1.2) ? square : tall;
  let h = fit === square ? CARD_HEIGHTS[0] : CARD_HEIGHTS[1];
  if (!fit) {
    probe.font = `${CARD_TEXT[1]}px ${family}`;
    const lines = wrap(probe, text, across);
    fit = { size: CARD_TEXT[1], lines, lh: Math.round(CARD_TEXT[1] * 1.6) };
    h = TOP + CARD_FOOT + lines.length * fit.lh;
  }
  const s = Math.min(1, side / Math.max(CARD_W, h), Math.sqrt(PICTURE_AREA / (CARD_W * h)));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(CARD_W * s);
  canvas.height = Math.round(h * s);
  const ctx = context(canvas);
  ctx.scale(s, s);
  // The text block in the middle of the room above the foot; each line's
  // baseline sits on a rule, and the rules run on, evenly, over the card.
  const block = fit.lines.length * fit.lh;
  const top = TOP + (h - TOP - CARD_FOOT - block) / 2;
  const baseline = (i: number) => top + i * fit.lh + fit.lh * 0.7;
  const rule = baseline(0) + fit.size * 0.14;
  ctx.fillStyle = PAPER;
  ctx.fillRect(0, 0, CARD_W, h);
  ctx.fillStyle = RULE;
  for (let y = rule - Math.ceil(rule / fit.lh) * fit.lh; y < h; y += fit.lh) if (y > 0) ctx.fillRect(0, y - 1, CARD_W, 2);
  ctx.fillStyle = MARGIN;
  ctx.fillRect(MARGIN_X, 0, 3, h);
  ctx.fillStyle = INK;
  ctx.font = `${fit.size}px ${family}`;
  fit.lines.forEach((line, i) => ctx.fillText(line, LEFT, baseline(i)));
  ctx.fillStyle = PENCIL;
  ctx.font = `${CREDIT}px ${uiFont()}`;
  ctx.textAlign = "right";
  ctx.fillText(credit, CARD_W - RIGHT, h - CARD_FOOT / 2 + CREDIT / 3);
  drawLog.step = "canvas";
  const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/png"));
  const { width, height } = canvas;
  canvas.width = canvas.height = 0;
  drawLog.canvases.push(`card ${width}x${height} ${blob ? "ok" : "failed"}`);
  if (!blob) throw new SaveError("canvas", `toBlob gave nothing for ${width}x${height}`);
  return blob;
}

export type Pdf = { pdf: Blob; firstPage: Blob }; // the first page as a picture, to show on the page

/** A4 pages, a block never split across two. */
async function a4Pages(make: Make, title: string, dpi: number): Promise<Pdf> {
  let page = a4Canvas(dpi);
  const { width: w, height: h } = page;
  drawLog.step = "canvas";
  drawLog.canvases.push(`A4 ${w}x${h} at ${dpi} dpi`);
  const s = w / PHONE_W;
  let ctx = context(page);
  const blocks = make(ctx, s, w - (LEFT + RIGHT) * s);
  const done: PdfPage[] = [];
  paper(ctx, w, h, s);
  let y = TOP * s;
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    const need = b.h + (b.keepWithNext && blocks[i + 1] ? blocks[i + 1].h : 0);
    if (y + need > h - BOTTOM * s && y > TOP * s) {
      done.push(await pageJpeg(page));
      page = a4Canvas(dpi);
      ctx = context(page);
      paper(ctx, w, h, s);
      y = TOP * s;
    }
    b.draw(ctx, y);
    y += b.h;
  }
  done.push(await pageJpeg(page));
  drawLog.canvases.push(`${done.length} page(s) ok`);
  drawLog.step = "PDF";
  return { pdf: await pagesToPdf(done, title), firstPage: new Blob([done[0].jpeg as BlobPart], { type: "image/jpeg" }) };
}

/** The visitor's font and the site's, loaded for exactly these letters, before
 * anything is drawn: a canvas doesn't wait for a font, it draws in a fallback. */
async function ready(family: string, texts: string[]) {
  drawLog.step = "font load";
  const text = texts.join(" ");
  // Each font on its own: one that fails to arrive (the grey boxes, the
  // site's typeface; an old page asking for files a newer version of the
  // site no longer has) is only a fallback, never a reason not to save.
  // Only the visitor's own font must be there.
  const results = await Promise.allSettled([document.fonts.load(`48px ${family}`, text), document.fonts.load(`48px ${uiFont()}`, text)]);
  results.forEach((r, i) => drawLog.fonts.push(`${i ? "site font" : "your font + grey boxes"}: ${r.status === "fulfilled" ? "ok" : errText(r.reason)}`));
  if (results.some((r) => r.status === "rejected")) drawLog.requests = await failedFontRequests();
  await document.fonts.ready;
  const name = family.match(/^"([^"]+)"/)?.[1];
  const loaded = !name || [...document.fonts].some((f) => f.family.replace(/"/g, "") === name && f.status === "loaded");
  drawLog.font = `${name ?? family}: ${loaded ? "loaded" : "not loaded"}`;
  if (!loaded) throw new SaveError("font", `${name} is not loaded`);
}

const sheetTexts = (sheet: Sheet) => [sheet.sample, ...sheet.groups.flatMap((g) => g.items.map((it) => it.text))];

/** The try-it text as a card to share, with `credit` (the site's name) at the foot. */
export async function textImage(text: string, family: string, credit: string): Promise<Blob> {
  await ready(family, [text, credit]);
  return smaller(PICTURE_SIDES, (side) => card(text.trim() || " ", family, credit, side));
}

export async function textPdf(text: string, family: string, title: string): Promise<Pdf> {
  await ready(family, [text]);
  return smaller(PDF_DPI, (dpi) => a4Pages((ctx, s, width) => textBlocks(ctx, text, `${TEXT * s}px ${family}`, s, width), title, dpi));
}

export async function sheetImage(sheet: Sheet, family: string): Promise<Blob> {
  await ready(family, sheetTexts(sheet));
  return smaller(PICTURE_SIDES, (side) => picture((ctx, s, width) => sheetBlocks(ctx, sheet, family, s, width), side));
}

export async function sheetPdf(sheet: Sheet, family: string): Promise<Pdf> {
  await ready(family, sheetTexts(sheet));
  return smaller(PDF_DPI, (dpi) => a4Pages((ctx, s, width) => sheetBlocks(ctx, sheet, family, s, width), sheet.title, dpi));
}
