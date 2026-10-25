"use client";

import { useEffect, useState } from "react";
import { useLang } from "@/lib/i18n";
import { chromeIntent, isAndroid, SaveError, type Saved, saveFile } from "@/lib/savefile";

type Made = { blob: Blob; name: string; title: string };
type State =
  | { kind: "idle" }
  | { kind: "making"; key: string }
  | { kind: "saved"; made: Made; how: Saved["how"]; app?: string; shown: boolean }
  | { kind: "error"; code: "font" | "canvas" | "other"; detail: string };

// Making a file and handing it over, for every "save" button: what happened
// is said under the buttons, and when the file can't be saved (an app's own
// browser, or a download that didn't arrive) it's shown on the page instead,
// to long-press.
export function useSaver() {
  const [state, setState] = useState<State>({ kind: "idle" });

  async function save(key: string, make: () => Promise<Made>) {
    setState({ kind: "making", key });
    let made: Made;
    try {
      made = await make();
    } catch (err) {
      const detail = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
      setState({ kind: "error", code: err instanceof SaveError ? err.code : "other", detail });
      return;
    }
    await handOver(made, false);
  }

  async function handOver(made: Made, tapped: boolean) {
    try {
      const out = await saveFile(made.blob, made.name, made.title, tapped);
      setState({ kind: "saved", made, how: out.how, app: out.how === "in-app" ? out.app : undefined, shown: out.how === "in-app" });
    } catch (err) {
      // Even the download couldn't start: show it here.
      setState({ kind: "saved", made, how: "downloaded", shown: true });
      console.error(err);
    }
  }

  const making = state.kind === "making" ? state.key : null;
  const note = <SaveNote state={state} onTap={(made) => void handOver(made, true)} onShow={() => state.kind === "saved" && setState({ ...state, shown: true })} />;
  return { save, making, note };
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
      </div>
    );
  }
  const { made, how, app, shown } = state;
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
    </div>
  );
}

/** The file on the page: a picture to long-press, a PDF to open, text to copy. */
function Shown({ made }: { made: Made }) {
  const { t } = useLang();
  const [url, setUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const type = made.blob.type;
  useEffect(() => {
    // A data: URL, not a blob: one: an app's browser can't always reach blob: URLs.
    const reader = new FileReader();
    reader.onload = () => setUrl(reader.result as string);
    reader.readAsDataURL(made.blob);
    return () => reader.abort();
  }, [made.blob]);
  if (!url) return null;
  if (type.startsWith("image/")) {
    return (
      <figure className="save-shown">
        <figcaption>{t("ছবিটার ওপর আঙুল চেপে রাখুন, তারপর “ছবি সেভ করুন”।", "Long-press the picture, then “Save image”.")}</figcaption>
        <img src={url} alt={made.title} />
      </figure>
    );
  }
  if (type === "application/pdf") {
    return (
      <p>
        <a className="button" href={url} target="_blank" rel="noopener" download={made.name}>
          {t("PDF-টা খুলুন", "Open the PDF")}
        </a>
      </p>
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
