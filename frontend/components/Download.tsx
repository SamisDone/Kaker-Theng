"use client";

import { useId, useState } from "react";
import { MISSING_FONT } from "@/components/RewardScreen";
import { useSaver } from "@/components/SaveNote";
import { ApiError, fileUrl, requestDownload } from "@/lib/api";
import { timeLeft } from "@/lib/bn";
import { useLang } from "@/lib/i18n";
import { type Sheet, sheetImage, sheetPdf, textPdf } from "@/lib/khata";

type State = { kind: "idle" } | { kind: "busy"; ahead?: number; waking?: boolean; eta?: number | null } | { kind: "error"; bn: string; en: string };

const SAMPLE = "আমি বাংলায় লিখি। কাকের ঠ্যাং বকের ঠ্যাং";
// "Bangla letters only": letters, signs and digits; no conjuncts, no English.
const BANGLA_LETTERS = new Set(["vowels", "consonants", "signs", "more-consonants", "phala", "digits"]);

// Below the try-it text: the font itself, for a computer; then, under
// "more", the font sheet (every letter, as a picture or a PDF), the try-it
// text as a PDF, and the font's name.
export function Download(props: {
  session: string | null;
  ready: boolean; // the server has built the font
  userFont: string | null; // ...and this browser has loaded it
  groups: Sheet["groups"]; // every letter in the font, by chapter
  text: string; // the try-it text
}) {
  const { t, num } = useLang();
  const id = useId();
  const [name, setName] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const { save, show, making, note } = useSaver();
  const fallback = t("আমার হাতের লেখা", "My Handwriting");
  const title = name.trim() || fallback;

  type Kind = "png" | "letters" | "pdf" | "text-pdf";
  /** How to make each file: the font sheet (picture, Bangla letters, PDF) or the try-it text as a PDF. */
  function maker(kind: Kind) {
    const family = `"${props.userFont}", ${MISSING_FONT}`;
    if (kind === "text-pdf") {
      return async () => {
        const { pdf, firstPage } = await textPdf(props.text, family, title);
        return { blob: pdf, preview: firstPage, name: "kaker-theng.pdf", title };
      };
    }
    const groups = kind === "letters" ? props.groups.filter((g) => BANGLA_LETTERS.has(g.id)) : props.groups;
    const sheet: Sheet = { title, subtitle: t("কাকের ঠ্যাং দিয়ে বানানো ফন্ট", "A font made with Kaker Theng"), sample: SAMPLE, groups };
    if (kind === "pdf") {
      return async () => {
        const { pdf, firstPage } = await sheetPdf(sheet, family);
        return { blob: pdf, preview: firstPage, name: "kaker-theng-font-sheet.pdf", title };
      };
    }
    return async () => ({ blob: await sheetImage(sheet, family), name: kind === "letters" ? "kaker-theng-bangla-letters.png" : "kaker-theng-font-sheet.png", title });
  }

  async function zip() {
    if (!props.session) return;
    setState({ kind: "busy" });
    try {
      const out = await requestDownload(props.session, title, (p) => setState({ kind: "busy", ahead: p.working ? 0 : p.ahead, waking: p.waking, eta: p.eta }));
      const a = document.createElement("a");
      a.href = fileUrl(props.session, out.file);
      a.download = out.file;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setState({ kind: "idle" });
    } catch (err) {
      const e = err instanceof ApiError ? err : new ApiError("error", "Something went wrong. Please try again.", "কিছু একটা ঠিক হয়নি। আবার চেষ্টা করুন।");
      setState({ kind: "error", bn: e.bn, en: e.message });
    }
  }

  let busy: string | null = null;
  if (state.kind === "busy") {
    busy = state.waking
      ? t("কাক ঘুম থেকে উঠছে…", "waking up the crow…")
      : state.ahead
        ? t(`আপনার আগে ${num(state.ahead)} জন আছে`, `${state.ahead} ${state.ahead === 1 ? "person" : "people"} ahead of you`)
        : t("ফন্ট বানাচ্ছি…", "making your font…");
    const left = timeLeft(state.eta);
    if (left) busy += ` · ${t(left[0], left[1])}`;
  }

  const can = Boolean(props.userFont) && making === null;
  const label = (key: string, bn: string, en: string) => (making === key ? t("বানাচ্ছি…", "making it…") : t(bn, en));
  // Each file: save (share sheet or download), or only show it on the page.
  const row = (kind: Kind, bn: string, en: string) => {
    const off = !can || (kind === "text-pdf" && !props.text.trim());
    return (
      <div className="output-row" key={kind}>
        <button type="button" className="button" disabled={off} onClick={() => void save(kind, maker(kind))}>
          {label(kind, bn, en)}
        </button>
        <button type="button" className="button show" disabled={off} onClick={() => void show(`${kind}-show`, maker(kind))}>
          {label(`${kind}-show`, "স্ক্রিনে দেখান", "Show on screen")}
        </button>
      </div>
    );
  };
  return (
    <div className="download" id="download">
      <button type="button" className="button big" disabled={!props.ready || state.kind === "busy"} onClick={zip}>
        {t("ফন্ট ডাউনলোড (কম্পিউটারের জন্য)", "Download the font (for a computer)")}
      </button>
      <p className="mono pencil formats">{t("zip: TTF আর WOFF2, লাইসেন্সসহ", "zip: TTF and WOFF2, with the licence")}</p>
      <p className="where-to-use">{t("ফোনে Canva বা PixelLab-এ ব্যবহার করুন; কম্পিউটারে ইনস্টল করুন।", "On phones, use it in Canva or PixelLab; on a computer, install it.")}</p>
      <div aria-live="polite">
        {!props.ready && <p>{t("কয়েকটা অক্ষর আঁকলে বা একটা পাতার ছবি দিলে নামানো যাবে।", "You can download once you've drawn a few letters or added a page photo.")}</p>}
        {busy && <p>{busy}</p>}
        {state.kind === "error" && (
          <p className="margin-note" role="alert">
            {t(state.bn, state.en)}
          </p>
        )}
      </div>

      <details className="more">
        <summary>{t("আরও", "More")}</summary>
        <label className="field" htmlFor={id}>
          {t("ফন্টের নাম", "Font name")}
          <input id={id} value={name} maxLength={40} autoComplete="off" onChange={(e) => setName(e.target.value)} placeholder={fallback} />
        </label>
        <div className="outputs">
          {row("png", "ফন্ট শিট: ছবি", "Font sheet: image")}
          {row("letters", "ছবি: শুধু বাংলা অক্ষর", "Image: Bangla letters only")}
          {row("pdf", "ফন্ট শিট: PDF", "Font sheet: PDF")}
          {row("text-pdf", "লেখাটা PDF হিসেবে", "The text as a PDF")}
        </div>
        <p className="outputs-note">
          {t(
            "ফন্ট শিট: আপনার আঁকা সব অক্ষর, আপনার ফন্টে; শুধু বাংলা অক্ষরেরটা ছোট, পাঠাতে সহজ। PDF A4-এ ছাপা যায়।",
            "The font sheet: every letter you drew, in your font; the Bangla letters one is shorter, easy to send. The PDFs print on A4.",
          )}
        </p>
        {note}
      </details>
    </div>
  );
}
