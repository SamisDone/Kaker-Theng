// The try-it text in the visitor's font, on khata paper, as a PNG: phones
// can't install a font, but they can post a picture of it.

const WIDTH = 1080; // px: a square-feed post's width
const SIZE = 56; // font size, px
const LINE = 96; // one rule per line
const MARGIN_X = 96; // the red margin line
const LEFT = 132; // text starts right of it
const RIGHT = 64;
const TOP = LINE; // first rule
const BOTTOM = LINE;

const PAPER = "#f4f0e6";
const RULE = "#b9c6e0";
const MARGIN = "#c2412d";
const INK = "#1d2140";

/** Lines of text that fit `width`, breaking between words. */
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

export async function textImage(text: string, family: string): Promise<Blob> {
  const font = `${SIZE}px ${family}`;
  await document.fonts.load(font, text);
  const probe = document.createElement("canvas").getContext("2d")!;
  probe.font = font;
  const lines = wrap(probe, text.trim() || " ", WIDTH - LEFT - RIGHT);

  const height = TOP + lines.length * LINE + BOTTOM;
  const canvas = document.createElement("canvas");
  canvas.width = WIDTH;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = PAPER;
  ctx.fillRect(0, 0, WIDTH, height);
  ctx.fillStyle = RULE;
  for (let y = TOP + LINE; y < height; y += LINE) ctx.fillRect(0, y - 1, WIDTH, 2);
  ctx.fillStyle = MARGIN;
  ctx.fillRect(MARGIN_X, 0, 3, height);

  ctx.font = font;
  ctx.fillStyle = INK;
  ctx.textBaseline = "alphabetic";
  lines.forEach((line, i) => ctx.fillText(line, LEFT, TOP + (i + 1) * LINE - 18)); // sits on the rule

  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("no image"))), "image/png"));
}
