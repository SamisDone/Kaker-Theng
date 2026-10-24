// Things to look at and share, drawn by the browser on khata paper: the
// try-it text, and the font sheet (every letter in the visitor's font).
// The same layout gives one tall picture sized for a phone, or A4 pages
// for a PDF. The canvas shapes Bangla as the page does.

import { a4Canvas, pagesToPdf } from "@/lib/pdf";

const PHONE_W = 1080; // px; everything below is in these units, scaled for A4
const LINE = 96; // rule spacing
const MARGIN_X = 96; // the red margin line
const LEFT = 132;
const RIGHT = 64;
const TOP = 96;
const BOTTOM = 96;
const TEXT = 56; // try-it text size
const COLS = 8; // font sheet grid

const PAPER = "#f4f0e6";
const RULE = "#b9c6e0";
const MARGIN = "#c2412d";
const INK = "#1d2140";
const PENCIL = "#6e685d";

export type Sheet = {
  title: string; // the font's name
  subtitle: string; // "made with Kaker Theng", in the screen's language
  sample: string; // a line in the font
  groups: { name: string; texts: string[] }[]; // chapters, with what was drawn
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
    const texts = [...new Set(group.texts)]; // a conjunct with two parts drawn shows once
    if (!texts.length) continue;
    blocks.push({
      keepWithNext: true,
      h: LINE * 0.75 * s,
      draw: (c, y) => {
        c.fillStyle = PENCIL;
        c.font = `${26 * s}px ${ui}`;
        c.fillText(group.name, LEFT * s, y + 60 * s);
      },
    });
    for (let i = 0; i < texts.length; i += COLS) {
      const row = texts.slice(i, i + COLS);
      blocks.push({
        h: cell + 8 * s,
        draw: (c, y) => {
          row.forEach((text, j) => {
            const x = LEFT * s + j * cell;
            c.fillStyle = PAPER;
            c.fillRect(x, y, cell, cell);
            c.strokeStyle = RULE;
            c.lineWidth = 1.5 * s;
            c.strokeRect(x + 0.75 * s, y + 0.75 * s, cell - 1.5 * s, cell - 1.5 * s);
            // The letter in the visitor's font, as large as fits.
            let size = cell * 0.52;
            c.font = `${size}px ${family}`;
            const w = c.measureText(text).width;
            if (w > cell * 0.82) size *= (cell * 0.82) / w;
            c.font = `${size}px ${family}`;
            c.fillStyle = INK;
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

/** One tall picture for a phone. */
async function picture(make: (ctx: CanvasRenderingContext2D, s: number, width: number) => Block[]): Promise<Blob> {
  const probe = document.createElement("canvas").getContext("2d")!;
  const blocks = make(probe, 1, PHONE_W - LEFT - RIGHT);
  const height = TOP + blocks.reduce((a, b) => a + b.h, 0) + BOTTOM;
  const canvas = document.createElement("canvas");
  canvas.width = PHONE_W;
  canvas.height = Math.round(height);
  const ctx = canvas.getContext("2d")!;
  paper(ctx, canvas.width, canvas.height, 1);
  let y = TOP;
  for (const b of blocks) {
    b.draw(ctx, y);
    y += b.h;
  }
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("no image"))), "image/png"));
}

/** A4 pages, a block never split across two. */
async function a4Pages(make: (ctx: CanvasRenderingContext2D, s: number, width: number) => Block[], title: string): Promise<Blob> {
  const first = a4Canvas();
  const s = first.width / PHONE_W;
  const blocks = make(first.getContext("2d")!, s, first.width - (LEFT + RIGHT) * s);
  const pages = [first];
  let ctx = first.getContext("2d")!;
  paper(ctx, first.width, first.height, s);
  let y = TOP * s;
  blocks.forEach((b, i) => {
    const need = b.h + (b.keepWithNext && blocks[i + 1] ? blocks[i + 1].h : 0);
    if (y + need > first.height - BOTTOM * s && y > TOP * s) {
      const next = a4Canvas();
      pages.push(next);
      ctx = next.getContext("2d")!;
      paper(ctx, next.width, next.height, s);
      y = TOP * s;
    }
    b.draw(ctx, y);
    y += b.h;
  });
  return pagesToPdf(pages, title);
}

async function ready(family: string, texts: string[]) {
  await Promise.all([document.fonts.load(`48px ${family}`, texts.join(" ")), document.fonts.load(`48px ${uiFont()}`, texts.join(" "))]);
}

export async function textImage(text: string, family: string): Promise<Blob> {
  await ready(family, [text]);
  return picture((ctx, s, width) => textBlocks(ctx, text, `${TEXT * s}px ${family}`, s, width));
}

export async function textPdf(text: string, family: string, title: string): Promise<Blob> {
  await ready(family, [text]);
  return a4Pages((ctx, s, width) => textBlocks(ctx, text, `${TEXT * s}px ${family}`, s, width), title);
}

export async function sheetImage(sheet: Sheet, family: string): Promise<Blob> {
  await ready(family, [sheet.sample, ...sheet.groups.flatMap((g) => g.texts)]);
  return picture((ctx, s, width) => sheetBlocks(ctx, sheet, family, s, width));
}

export async function sheetPdf(sheet: Sheet, family: string): Promise<Blob> {
  await ready(family, [sheet.sample, ...sheet.groups.flatMap((g) => g.texts)]);
  return a4Pages((ctx, s, width) => sheetBlocks(ctx, sheet, family, s, width), sheet.title);
}
