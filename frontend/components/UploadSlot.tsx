"use client";

import { useId } from "react";
import { fileUrl, type PageInfo, templateUrl } from "@/lib/api";
import { cornerBn, timeLeft } from "@/lib/bn";
import { useLang } from "@/lib/i18n";

export type SlotState =
  | { kind: "idle" }
  | { kind: "busy"; step: "shrinking" | "sending" | "queued" | "reading" | "waking"; ahead?: number; eta?: number | null }
  | { kind: "error"; bn: string; en: string; code?: string };

const STEP: Record<string, [string, string]> = {
  shrinking: ["ছবি ছোট করছি…", "resizing the photo…"],
  sending: ["ছবি পাঠাচ্ছি…", "sending the photo…"],
  reading: ["হাতের লেখা পড়ছি…", "reading your handwriting…"],
  waking: ["কাক ঘুম থেকে উঠছে…", "waking up the crow…"],
};

function statusText(s: Extract<SlotState, { kind: "busy" }>, num: (n: number) => string): [string, string] {
  let [bn, en] = STEP[s.step] ?? ["", ""];
  if (s.step === "queued") {
    const n = s.ahead ?? 1;
    [bn, en] = [`আপনার আগে ${num(n)} জন আছে`, `${n} ${n === 1 ? "person" : "people"} ahead of you`];
  }
  const left = s.step === "queued" || s.step === "reading" ? timeLeft(s.eta) : null;
  return left ? [`${bn} · ${left[0]}`, `${en} · ${left[1]}`] : [bn, en];
}

// One page: take or pick its photo, then see how it was read.
export function UploadSlot(props: {
  page: number;
  session: string | null;
  info: PageInfo | undefined;
  state: SlotState;
  note: { bn: string; en: string } | null;
  onPhoto: (file: File) => void;
}) {
  const { t, num } = useLang();
  const id = useId();
  const { page, info, state } = props;
  const busy = state.kind === "busy";
  const bad = info?.cells.filter((c) => c.status !== "ok") ?? [];
  const missing = bad.filter((c) => c.status === "missing");
  const outside = bad.filter((c) => c.status === "touches_edge");
  const total = info?.cells.length ?? 0;

  return (
    <div className="slot">
      <label className="drop" htmlFor={id}>
        {info ? t("আবার ছবি দিন", "Replace with a new photo") : t(`পাতা ${num(page)}-এর ছবি তুলুন`, `Photograph page ${page}`)}
        <input
          id={id}
          type="file"
          accept="image/*"
          capture="environment"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) props.onPhoto(file);
          }}
        />
      </label>

      <div className="status" aria-live="polite">
        {busy && <p>{t(...statusText(state, (n) => num(n)))}</p>}
      </div>

      {state.kind === "error" && (
        <p className="margin-note" role="alert">
          {t(state.bn, state.en)}{" "}
          {state.code === "old_template" && (
            <a href={templateUrl()} target="_blank" rel="noopener">
              {t("নতুন টেমপ্লেট", "current template")}
            </a>
          )}
        </p>
      )}
      {props.note && <p className="margin-note">{t(props.note.bn, props.note.en)}</p>}

      {info && props.session && (
        <div className="result">
          <img
            src={fileUrl(props.session, info.thumbnail)}
            alt={
              bad.length
                ? t(`পাতা ${num(page)}-এর সোজা করা ছবি, লাল দাগ দেওয়া ${num(bad.length)}টা ঘর পড়া যায়নি।`, `Straightened photo of page ${page}; ${bad.length} cells circled in red couldn't be read.`)
                : t(`পাতা ${num(page)}-এর সোজা করা ছবি, সব ঘর পড়া গেছে।`, `Straightened photo of page ${page}; every cell was read.`)
            }
          />
          <div>
            <p>{t(`${num(total)}টার মধ্যে ${num(total - missing.length)}টা ঘর পড়া গেছে।`, `${total - missing.length} of ${total} cells read.`)}</p>
            {info.missing_corners.length > 0 && (
              <p className="margin-note">
                {t(
                  `${info.missing_corners.map(cornerBn).join(", ")} কোণের চৌকো দেখা যায়নি, তবু পড়া গেছে।`,
                  `Couldn't see the ${info.missing_corners.join(", ")} corner, but the page was still read.`,
                )}
              </p>
            )}
            {missing.length > 0 && (
              <p className="margin-note">
                {t("খালি, তাই ফন্টে থাকবে না: ", "Empty, so not in the font: ")}
                <span lang="bn">{missing.map((c) => c.text).join("  ")}</span>
                {t(" (পরে এঁকে নিতে পারেন)", " (you can draw them later)")}
              </p>
            )}
            {outside.length > 0 && (
              <p className="margin-note">
                {t("ঘরের বাইরে গেছে, কাটা পড়তে পারে: ", "Ran out of the box, may be cut off: ")}
                <span lang="bn">{outside.map((c) => c.text).join("  ")}</span>
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
