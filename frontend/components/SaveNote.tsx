"use client";

import { useEffect, useState } from "react";
import { useLang } from "@/lib/i18n";
import { drawLog, resetDrawLog } from "@/lib/khata";
import { chromeIntent, inAppBrowser, isAndroid, SaveError, type Saved, type SaveTrace, saveFile } from "@/lib/savefile";

type Made = { blob: Blob; name: string; title: string; preview?: Blob }; // preview: a PDF's first page, as a picture
type State =
  | { kind: "idle" }
  | { kind: "making"; key: string }
  | { kind: "saved"; made: Made; how: Saved["how"] | "shown"; app?: string; shown: boolean; failed: boolean; key: string; trace: SaveTrace }
  | { kind: "error"; code: "font" | "canvas" | "other"; detail: string; report: string };

const errText = (err: unknown) => (err instanceof Error ? `${err.name}: ${err.message}` : String(err));

/** Everything about one save, to paste into a message: the browser, the way tried, what broke. */
function report(action: string, trace: SaveTrace, error: unknown, made: Made | null): string {
  let canShare = trace.canShare;
  if (canShare === null && typeof navigator.canShare === "function") {
    try {
      canShare = navigator.canShare({ files: [new File(["x"], "test.png", { type: "image/png" })] });
    } catch {
      canShare = false;
    }
  }
  return [
    "Kaker Theng: save report",
    `time: ${new Date().toISOString()}`,
    `action: ${action}`,
    `browser: ${navigator.userAgent}`,
    `screen: ${innerWidth}x${innerHeight} @${devicePixelRatio}`,
    `in-app browser: ${inAppBrowser() ?? "no"}`,
    `can share files: ${canShare === null ? "no share in this browser" : canShare ? "yes" : "no"}`,
    `path: ${trace.path.join(" -> ") || "none: the file wasn't made"}`,
    `error: ${error ? errText(error) : "none"}`,
    `canvas: ${drawLog.canvases.join(", ") || "none drawn"}`,
    `font: ${drawLog.font || "not checked"}`,
    `file: ${made ? `${made.name}, ${made.blob.type}, ${made.blob.size} bytes` : "not made"}`,
  ].join("\n");
}

// Making a file and handing it over, for every "save" button: what happened
// is said under the buttons; "show on screen" puts the file on the page to
// long-press, with no share or download at all; and whenever saving fails
// there is a report to copy and send.
export function useSaver() {
  const [state, setState] = useState<State>({ kind: "idle" });

  async function made(key: string, action: string, make: () => Promise<Made>, trace: SaveTrace): Promise<Made | null> {
    setState({ kind: "making", key });
    resetDrawLog();
    try {
      return await make();
    } catch (err) {
      setState({ kind: "error", code: err instanceof SaveError ? err.code : "other", detail: errText(err), report: report(action, trace, err, null) });
      return null;
    }
  }

  async function save(key: string, make: () => Promise<Made>) {
    const trace: SaveTrace = { canShare: null, path: [] };
    const m = await made(key, `save ${key}`, make, trace);
    if (m) await handOver(m, false, key, trace);
  }

  /** Made and shown on the page, nothing else: no share, no download. */
  async function show(key: string, make: () => Promise<Made>) {
    const trace: SaveTrace = { canShare: null, path: ["shown on the page"] };
    const m = await made(key, `show ${key}`, make, trace);
    if (m) setState({ kind: "saved", made: m, how: "shown", shown: true, failed: false, key, trace });
  }

  async function handOver(m: Made, tapped: boolean, key: string, trace: SaveTrace) {
    try {
      const out = await saveFile(m.blob, m.name, m.title, tapped, trace);
      const shareFailed = out.how === "downloaded" && trace.path.some((p) => p.startsWith("share failed"));
      setState({ kind: "saved", made: m, how: out.how, app: out.how === "in-app" ? out.app : undefined, shown: out.how === "in-app", failed: out.how === "in-app" || shareFailed, key, trace });
    } catch (err) {
      // Even the download couldn't start: show it here.
      trace.path.push(`failed (${errText(err)})`);
      setState({ kind: "saved", made: m, how: "downloaded", shown: true, failed: true, key, trace });
    }
  }

  const making = state.kind === "making" ? state.key : null;
  const note = (
    <SaveNote
      state={state}
      onTap={(m) => state.kind === "saved" && void handOver(m, true, state.key, state.trace)}
      onShow={() => state.kind === "saved" && setState({ ...state, shown: true, failed: true, trace: { ...state.trace, path: [...state.trace.path, "not in Downloads: shown on the page"] } })}
    />
  );
  return { save, show, making, note };
}

function SaveNote({ state, onTap, onShow }: { state: State; onTap: (made: Made) => void; onShow: () => void }) {
  const { t } = useLang();
  if (state.kind === "idle" || state.kind === "making") return null;
  if (state.kind === "error") {
    return (
      <div className="save-note" role="alert">
        <p className="margin-note">
          {state.code === "font"
            ? t("আপনার ফন্ট এখনও লোড হয়নি। একটু পরে আবার চাপুন।", "Your font hasn't loaded yet. Try again in a moment.")
            : state.code === "canvas"
              ? t("এই ফোনে এত বড় ছবি বানানো গেল না।", "This phone couldn't make a picture that big.")
              : t("ফাইলটা বানানো গেল না।", "Couldn't make the file.")}
        </p>
        <p className="mono pencil save-detail" lang="en">
          {state.detail}
        </p>
        <CopyReport text={state.report} />
      </div>
    );
  }
  const { made, how, app, shown, failed } = state;
  return (
    <div className="save-note" aria-live="polite">
      {how === "tap" && (
        <p>
          {t("তৈরি। সেভ করতে আরেকবার চাপুন।", "Ready. Tap once more to save it.")}{" "}
          <button type="button" className="button primary" onClick={() => onTap(made)}>
            {t("সেভ করুন", "Save it")}
          </button>
        </p>
      )}
      {how === "downloaded" && !shown && (
        <p>
          {t("ডাউনলোড-এ রাখা হয়েছে।", "Saved to Downloads.")}{" "}
          <button type="button" className="link-button" onClick={onShow}>
            {t("পাননি? এখানে দেখান", "Not there? Show it here")}
          </button>
        </p>
      )}
      {how === "in-app" && (
        <>
          <p className="margin-note">
            {app
              ? t(`${app}-এর ভেতরের ব্রাউজার ফাইল সেভ করতে দেয় না।`, `${app}'s built-in browser doesn't let a site save files.`)
              : t("এই অ্যাপের ভেতরের ব্রাউজার ফাইল সেভ করতে দেয় না।", "This app's built-in browser doesn't let a site save files.")}
          </p>
          <p>
            {isAndroid() ? (
              <a className="button" href={chromeIntent()}>
                {t("Chrome-এ খুলুন", "Open in Chrome")}
              </a>
            ) : (
              t("⋯ মেনু থেকে “ব্রাউজারে খুলুন” চাপুন।", "Use the ⋯ menu: “Open in browser”.")
            )}
          </p>
          <p className="pencil">
            {t("আঁকা অক্ষরগুলো এই ব্রাউজারেই থাকে; Chrome-এ নতুন করে শুরু হবে।", "Your letters stay in this browser; Chrome starts fresh.")}
          </p>
        </>
      )}
      {shown && <Shown made={made} />}
      {failed && <CopyReport text={report(`save ${state.key}`, state.trace, null, made)} />}
    </div>
  );
}

/** The report, copied with one tap; where copying isn't allowed, shown to select by hand. */
function CopyReport({ text }: { text: string }) {
  const { t } = useLang();
  const [state, setState] = useState<"idle" | "copied" | "manual">("idle");
  return (
    <div className="save-report">
      <button
        type="button"
        className="button"
        onClick={() =>
          navigator.clipboard
            .writeText(text)
            .then(() => setState("copied"))
            .catch(() => setState("manual"))
        }
      >
        {state === "copied" ? t("কপি হয়েছে: মেসেজে পেস্ট করে পাঠান", "Copied: paste it into a message") : t("সমস্যার বিবরণ কপি করুন", "Copy error details")}
      </button>
      {state === "manual" && (
        <>
          <p className="pencil">{t("কপি করা গেল না। নিচের লেখাটা চেপে ধরে কপি করুন:", "Couldn't copy. Long-press the text below to copy it:")}</p>
          <textarea className="mono save-report-text" readOnly value={text} rows={8} onFocus={(e) => e.currentTarget.select()} />
        </>
      )}
    </div>
  );
}

/** A data: URL of a blob, made on the page: an app's browser can't always reach blob: URLs. */
function useDataUrl(blob: Blob | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!blob) return;
    const reader = new FileReader();
    reader.onload = () => setUrl(reader.result as string);
    reader.readAsDataURL(blob);
    return () => reader.abort();
  }, [blob]);
  return url;
}

/** The file on the page: a picture to long-press, a PDF's first page and a link to the whole, text to copy. */
function Shown({ made }: { made: Made }) {
  const { t } = useLang();
  const [copied, setCopied] = useState(false);
  const type = made.blob.type;
  const pdf = type === "application/pdf";
  const url = useDataUrl(made.blob);
  const picture = useDataUrl(pdf ? made.preview : type.startsWith("image/") ? made.blob : undefined);
  if (!url) return null;
  if (type.startsWith("image/") || pdf) {
    return (
      <figure className="save-shown">
        <figcaption>
          {pdf
            ? t("প্রথম পাতা, ছবি হিসেবে: আঙুল চেপে রেখে “ছবি সেভ করুন”।", "The first page as a picture: long-press it, then “Save image”.")
            : t("ছবিটার ওপর আঙুল চেপে রাখুন, তারপর “ছবি সেভ করুন”।", "Long-press the picture, then “Save image”.")}
        </figcaption>
        {pdf && (
          <p>
            <a className="button" href={url} target="_blank" rel="noopener" download={made.name}>
              {t("PDF-টা খুলুন", "Open the PDF")}
            </a>
          </p>
        )}
        {picture && <img src={picture} alt={made.title} />}
      </figure>
    );
  }
  return (
    <p>
      <button
        type="button"
        className="button"
        onClick={() =>
          void made.blob
            .text()
            .then((s) => navigator.clipboard.writeText(s))
            .then(() => setCopied(true))
        }
      >
        {copied ? t("কপি হয়েছে: মেসেজে পেস্ট করে পাঠান", "Copied: paste it into a message") : t("কপি করুন", "Copy it")}
      </button>
    </p>
  );
}
