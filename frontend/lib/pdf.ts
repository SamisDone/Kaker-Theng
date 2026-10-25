// A PDF of A4 pages, each one picture. The pages are drawn on a canvas by
// the browser, which shapes Bangla the way the screen does (ি before its
// letter, conjuncts joined); a PDF library would have to shape it again.

import { SaveError } from "@/lib/savefile";

const A4_PT: [number, number] = [595.28, 841.89];

/** UTF-16BE hex string with a byte-order mark: PDF text for any script. */
function pdfText(s: string): string {
  let hex = "FEFF";
  for (let i = 0; i < s.length; i++) hex += s.charCodeAt(i).toString(16).padStart(4, "0").toUpperCase();
  return `<${hex}>`;
}

export type PdfPage = { jpeg: Uint8Array; width: number; height: number };

/** A finished page as a JPEG; the canvas is let go, so a phone never holds every page at once. */
export async function pageJpeg(canvas: HTMLCanvasElement): Promise<PdfPage> {
  const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/jpeg", 0.9));
  const { width, height } = canvas;
  canvas.width = canvas.height = 0;
  if (!blob) throw new SaveError("canvas", `toBlob gave nothing for a ${width}x${height} page`);
  return { jpeg: new Uint8Array(await blob.arrayBuffer()), width, height };
}

export async function pagesToPdf(pages: PdfPage[], title: string): Promise<Blob> {
  const enc = new TextEncoder();
  const parts: Uint8Array[] = [];
  const offsets: number[] = [];
  let size = 0;
  const put = (chunk: string | Uint8Array) => {
    const bytes = typeof chunk === "string" ? enc.encode(chunk) : chunk;
    parts.push(bytes);
    size += bytes.length;
  };
  const obj = (n: number, body: string | (string | Uint8Array)[]) => {
    offsets[n] = size;
    put(`${n} 0 obj\n`);
    for (const p of Array.isArray(body) ? body : [body]) put(p);
    put("\nendobj\n");
  };

  // 1 catalog, 2 page tree, 3 info, then three objects per page.
  const n = pages.length;
  const pageObj = (i: number) => 4 + 3 * i;
  put("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");
  obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
  obj(2, `<< /Type /Pages /Kids [${pages.map((_, i) => `${pageObj(i)} 0 R`).join(" ")}] /Count ${n} >>`);
  obj(3, `<< /Title ${pdfText(title)} /Producer (Kaker Theng) >>`);
  const [w, h] = A4_PT;
  for (let i = 0; i < n; i++) {
    const img = pages[i].jpeg;
    const draw = `q ${w} 0 0 ${h} 0 0 cm /Im0 Do Q`;
    obj(pageObj(i), `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Resources << /XObject << /Im0 ${pageObj(i) + 2} 0 R >> >> /Contents ${pageObj(i) + 1} 0 R >>`);
    obj(pageObj(i) + 1, [`<< /Length ${draw.length} >>\nstream\n`, draw, "\nendstream"]);
    obj(pageObj(i) + 2, [
      `<< /Type /XObject /Subtype /Image /Width ${pages[i].width} /Height ${pages[i].height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${img.length} >>\nstream\n`,
      img,
      "\nendstream",
    ]);
  }
  const count = pageObj(n);
  const xref = size;
  put(`xref\n0 ${count}\n0000000000 65535 f \n`);
  for (let i = 1; i < count; i++) put(`${String(offsets[i]).padStart(10, "0")} 00000 n \n`);
  put(`trailer\n<< /Size ${count} /Root 1 0 R /Info 3 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return new Blob(parts as BlobPart[], { type: "application/pdf" });
}

/** A4 page canvas at `dpi`. */
export function a4Canvas(dpi = 200): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = Math.round((A4_PT[0] / 72) * dpi);
  c.height = Math.round((A4_PT[1] / 72) * dpi);
  return c;
}
