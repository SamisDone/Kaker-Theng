"use client";

import { useId, useState } from "react";
import { ApiError, fileUrl, requestDownload } from "@/lib/api";
import { bnNum } from "@/lib/bn";

type State = { kind: "idle" } | { kind: "busy"; ahead?: number; waking?: boolean } | { kind: "error"; bn: string; en: string };

export function Download({ session, ready }: { session: string | null; ready: boolean }) {
  const id = useId();
  const [name, setName] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });

  async function get(format: "ttf" | "woff2") {
    if (!session) return;
    if (!name.trim()) {
      setState({ kind: "error", bn: "ফন্টের একটা নাম দিন।", en: "Give your font a name." });
      return;
    }
    setState({ kind: "busy" });
    try {
      const out = await requestDownload(session, name, format, (p) => setState({ kind: "busy", ahead: p.working ? 0 : p.ahead, waking: p.waking }));
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

  const busy = state.kind === "busy";
  return (
    <div>
      <label className="field" htmlFor={id}>
        <span lang="bn">ফন্টের নাম</span>
        <span className="en-sub" lang="en">
          Font name
        </span>
        <input id={id} value={name} maxLength={40} autoComplete="off" onChange={(e) => setName(e.target.value)} placeholder="আমার হাতের লেখা" />
      </label>
      <div className="download-buttons">
        <button type="button" className="button" disabled={!ready || busy} onClick={() => get("ttf")}>
          TTF
        </button>
        <button type="button" className="button" disabled={!ready || busy} onClick={() => get("woff2")}>
          WOFF2
        </button>
        <span className="mono">zip · with licence</span>
      </div>
      <div aria-live="polite">
        {!ready && (
          <p>
            একটা পাতা পড়া হলে নামানো যাবে।
            <span className="en-sub" lang="en">
              You can download once a page has been read.
            </span>
          </p>
        )}
        {busy && (
          <p>
            {state.waking
              ? "কাক ঘুম থেকে উঠছে…"
              : state.ahead
                ? `আপনার আগে ${bnNum(state.ahead)} জন আছে`
                : "ফন্ট বানাচ্ছি…"}
            <span className="en-sub" lang="en">
              {state.waking ? "waking up the crow…" : state.ahead ? `${state.ahead} ${state.ahead === 1 ? "person" : "people"} ahead of you` : "making your font…"}
            </span>
          </p>
        )}
        {state.kind === "error" && (
          <p className="margin-note" role="alert">
            {state.bn}
            <span className="en-sub en" lang="en">
              {state.en}
            </span>
          </p>
        )}
      </div>
    </div>
  );
}
