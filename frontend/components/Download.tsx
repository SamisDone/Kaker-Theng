"use client";

import { useId, useState } from "react";
import { MISSING_FONT } from "@/components/RewardScreen";
import { useSaver } from "@/components/SaveNote";
import { ApiError, fileUrl, requestDownload } from "@/lib/api";
import { timeLeft } from "@/lib/bn";
import { useLang } from "@/lib/i18n";
import { type Sheet, sheetImage, sheetPdf } from "@/lib/khata";

type State = { kind: "idle" } | { kind: "busy"; ahead?: number; waking?: boolean; eta?: number | null } | { kind: "error"; bn: string; en: string };

const SAMPLE = "আমি বাংলায় লিখি। কাকের ঠ্যাং বকের ঠ্যাং";
// "Bangla letters only": letters, signs and digits; no conjuncts, no English.
const BANGLA_LETTERS = new Set(["vowels", "consonants", "signs", "phala", "digits"]);

// What a visitor takes away. First what any phone can open, look at and
// share: the font sheet as a picture or a PDF. Then, for a computer, the
// font itself.
export function Download(props: {
  session: string | null;
  ready: boolean; // the server has built the font
  userFont: string | null; // ...and this browser has loaded it
  groups: Sheet["groups"]; // every letter in the font, by chapter
}) {
  const { t, num } = useLang();
  const id = useId();
  const [name, setName] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const { save, making, note } = useSaver();
  const fallback = t("আমার হাতের লেখা", "My Handwriting");
  const title = name.trim() || fallback;

  function sheet(kind: "png" | "letters" | "pdf") {
    if (!props.userFont) return;
    const family = `"${props.userFont}", ${MISSING_FONT}`;
    const groups = kind === "letters" ? props.groups.filter((g) => BANGLA_LETTERS.has(g.id)) : props.groups;
    const sheet: Sheet = { title, subtitle: t("কাকের ঠ্যাং দিয়ে বানানো ফন্ট", "A font made with Kaker Theng"), sample: SAMPLE, groups };
    void save(kind, async () => ({
      blob: kind === "pdf" ? await sheetPdf(sheet, family) : await sheetImage(sheet, family),
      name: kind === "letters" ? "kaker-theng-bangla-letters.png" : `kaker-theng-font-sheet.${kind}`,
      title,
    }));
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

  const canSheet = Boolean(props.userFont) && making === null;
  return (
    <div className="download" id="download">
      <h3>{t("নিয়ে যান", "Take it with you")}</h3>
      <label className="field" htmlFor={id}>
        {t("ফন্টের নাম", "Font name")}
        <input id={id} value={name} maxLength={40} autoComplete="off" onChange={(e) => setName(e.target.value)} placeholder={fallback} />
      </label>
      <div className="outputs">
        <button type="button" className="button big primary" disabled={!canSheet} onClick={() => sheet("png")}>
          {making === "png" ? t("বানাচ্ছি…", "making it…") : t("ফন্ট শিট: ছবি", "Font sheet: image")}
        </button>
        <button type="button" className="button" disabled={!canSheet} onClick={() => sheet("letters")}>
          {making === "letters" ? t("বানাচ্ছি…", "making it…") : t("ছবি: শুধু বাংলা অক্ষর", "Image: Bangla letters only")}
        </button>
        <button type="button" className="button big" disabled={!canSheet} onClick={() => sheet("pdf")}>
          {making === "pdf" ? t("বানাচ্ছি…", "making it…") : t("ফন্ট শিট: PDF", "Font sheet: PDF")}
        </button>
      </div>
      <p className="outputs-note">
        {t(
          "আপনার আঁকা সব অক্ষর, আপনার ফন্টে। ছবিটা গ্যালারিতে রাখুন বা পাঠান; শুধু বাংলা অক্ষরেরটা ছোট, পাঠাতে সহজ। PDF-টা A4-এ ছাপা যায়।",
          "Every letter you drew, in your font. Keep the picture or send it; the Bangla letters one is shorter, easy to send. The PDF prints on A4.",
        )}
      </p>
      {note}

      <div className="install">
        <button type="button" className="button" disabled={!props.ready || state.kind === "busy"} onClick={zip}>
          {t("কম্পিউটারে ইনস্টল করার জন্য (.ttf)", "To install on a computer (.ttf)")}
        </button>
        <p className="mono pencil formats">{t("zip: TTF আর WOFF2, লাইসেন্সসহ", "zip: TTF and WOFF2, with the licence")}</p>
        <p className="where-to-use">{t("ফোনে Canva বা PixelLab-এ ব্যবহার করুন; কম্পিউটারে ইনস্টল করুন।", "On phones, use it in Canva or PixelLab; on a computer, install it.")}</p>
      </div>
      <div aria-live="polite">
        {!props.ready && <p>{t("কয়েকটা অক্ষর আঁকলে বা একটা পাতার ছবি দিলে নামানো যাবে।", "You can download once you've drawn a few letters or added a page photo.")}</p>}
        {busy && <p>{busy}</p>}
        {state.kind === "error" && (
          <p className="margin-note" role="alert">
            {t(state.bn, state.en)}
          </p>
        )}
      </div>
    </div>
  );
}
