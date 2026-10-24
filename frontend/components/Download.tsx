"use client";

import { useId, useState } from "react";
import { ApiError, fileUrl, requestDownload } from "@/lib/api";
import { timeLeft } from "@/lib/bn";
import { useLang } from "@/lib/i18n";

type State = { kind: "idle" } | { kind: "busy"; ahead?: number; waking?: boolean; eta?: number | null } | { kind: "error"; bn: string; en: string };

export function Download({ session, ready }: { session: string | null; ready: boolean }) {
  const { t, num } = useLang();
  const id = useId();
  const [name, setName] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const fallback = t("আমার হাতের লেখা", "My Handwriting");

  async function get() {
    if (!session) return;
    setState({ kind: "busy" });
    try {
      const out = await requestDownload(session, name.trim() || fallback, (p) => setState({ kind: "busy", ahead: p.working ? 0 : p.ahead, waking: p.waking, eta: p.eta }));
      const a = document.createElement("a");
      a.href = fileUrl(session, out.file);
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

  return (
    <div className="download">
      <label className="field" htmlFor={id}>
        {t("ফন্টের নাম", "Font name")}
        <input id={id} value={name} maxLength={40} autoComplete="off" onChange={(e) => setName(e.target.value)} placeholder={fallback} />
      </label>
      <button type="button" className="button big primary" disabled={!ready || state.kind === "busy"} onClick={get}>
        {t("ডাউনলোড", "Download")}
      </button>
      <p className="mono pencil formats">{t("zip: TTF আর WOFF2, লাইসেন্সসহ", "zip: TTF and WOFF2, with the licence")}</p>
      <p className="where-to-use">{t("ফোনে Canva বা PixelLab-এ ব্যবহার করুন; কম্পিউটারে ইনস্টল করুন।", "On phones, use it in Canva or PixelLab; on a computer, install it.")}</p>
      <div aria-live="polite">
        {!ready && <p>{t("কয়েকটা অক্ষর আঁকলে বা একটা পাতার ছবি দিলে নামানো যাবে।", "You can download once you've drawn a few letters or added a page photo.")}</p>}
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
