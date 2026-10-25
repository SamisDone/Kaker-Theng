// Hand a file to the visitor: the phone's share sheet where the browser can
// share files (save to photos, send on WhatsApp...), a download otherwise.
// Inside an app's own browser (Facebook, Messenger, Instagram) a download
// goes nowhere, so the caller shows the file on the page instead.

export type Saved =
  | { how: "shared" | "downloaded" | "cancelled" }
  | { how: "tap" } // the share sheet wants a fresh tap: making the file took too long
  | { how: "in-app"; app: string }; // an app's browser: no share, and downloads fail

/** Why a file couldn't be made: the visitor's font, or the canvas (too big for this phone). */
export class SaveError extends Error {
  constructor(
    readonly code: "font" | "canvas",
    message: string,
  ) {
    super(message);
    this.name = "SaveError";
  }
}

const IN_APP: [RegExp, string][] = [
  [/Messenger|FB_IAB\/MESSENGER|FBAN\/MessengerForiOS/i, "Messenger"],
  [/Instagram/i, "Instagram"],
  [/FBAN|FBAV|FB_IAB|FB4A|FBIOS/i, "Facebook"],
  [/MicroMessenger/i, "WeChat"],
  [/\bLine\//i, "LINE"],
  [/TikTok|musical_ly|BytedanceWebview/i, "TikTok"],
  [/; wv\)/, ""], // some other app's Android WebView
];

/** The app whose built-in browser this is ("" if unknown), or null in a real browser. */
export function inAppBrowser(): string | null {
  const ua = navigator.userAgent;
  for (const [re, app] of IN_APP) if (re.test(ua)) return app;
  return null;
}

export const isAndroid = () => /Android/i.test(navigator.userAgent);

/** This page, opened in Chrome from an Android app's browser. */
export function chromeIntent(): string {
  const { host, pathname, search } = location;
  return `intent://${host}${pathname}${search}#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=${encodeURIComponent(location.href)};end`;
}

/** `tapped`: called straight from a tap, so a refused share isn't asked for again. */
export async function saveFile(blob: Blob, name: string, title: string, tapped = false): Promise<Saved> {
  const file = new File([blob], name, { type: blob.type });
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title });
      return { how: "shared" };
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return { how: "cancelled" };
      // The tap that started this has expired: one more tap shares it.
      if (err instanceof DOMException && err.name === "NotAllowedError" && !tapped) return { how: "tap" };
      // Share failed for another reason: fall back to a download.
    }
  }
  const app = inAppBrowser();
  if (app !== null) return { how: "in-app", app };
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return { how: "downloaded" };
}
