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
  const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/png"));
  const { width, height } = canvas;
  canvas.width = canvas.height = 0; // let the memory go now, not at the next garbage collection
  if (!blob) throw new SaveError("canvas", `toBlob gave nothing for ${width}x${height}`);
  return blob;
}

/** A4 pages, a block never split across two. */
async function a4Pages(make: Make, title: string, dpi: number): Promise<Blob> {
  let page = a4Canvas(dpi);
  const { width: w, height: h } = page;
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
  return pagesToPdf(done, title);
}

/** The visitor's font and the site's, loaded for exactly these letters, before
 * anything is drawn: a canvas doesn't wait for a font, it draws in a fallback. */
async function ready(family: string, texts: string[]) {
  const text = texts.join(" ");
  await Promise.all([document.fonts.load(`48px ${family}`, text), document.fonts.load(`48px ${uiFont()}`, text)]);
  await document.fonts.ready;
  const name = family.match(/^"([^"]+)"/)?.[1];
  if (name && ![...document.fonts].some((f) => f.family.replace(/"/g, "") === name && f.status === "loaded")) {
    throw new SaveError("font", `${name} is not loaded`);
  }
}

const sheetTexts = (sheet: Sheet) => [sheet.sample, ...sheet.groups.flatMap((g) => g.items.map((it) => it.text))];

export async function textImage(text: string, family: string): Promise<Blob> {
  await ready(family, [text]);
  return smaller(PICTURE_SIDES, (side) => picture((ctx, s, width) => textBlocks(ctx, text, `${TEXT * s}px ${family}`, s, width), side));
}

export async function textPdf(text: string, family: string, title: string): Promise<Blob> {
  await ready(family, [text]);
  return smaller(PDF_DPI, (dpi) => a4Pages((ctx, s, width) => textBlocks(ctx, text, `${TEXT * s}px ${family}`, s, width), title, dpi));
}

export async function sheetImage(sheet: Sheet, family: string): Promise<Blob> {
  await ready(family, sheetTexts(sheet));
  return smaller(PICTURE_SIDES, (side) => picture((ctx, s, width) => sheetBlocks(ctx, sheet, family, s, width), side));
}

export async function sheetPdf(sheet: Sheet, family: string): Promise<Blob> {
  await ready(family, sheetTexts(sheet));
  return smaller(PDF_DPI, (dpi) => a4Pages((ctx, s, width) => sheetBlocks(ctx, sheet, family, s, width), sheet.title, dpi));
}
