import type { SessionMeta } from "@/lib/api";
import { bnNum, pct } from "@/lib/bn";

// How much real Bangla text the font renders correctly (conjuncts, reph,
// phala, measured against Bangla Wikipedia), updated after every page.
export function Coverage({ meta, targets }: { meta: SessionMeta | null; targets: { pages_1_2: number; all_pages: number } | null }) {
  if (!meta || meta.coverage === undefined) return null;
  const has2 = Boolean(meta.pages["2"]);
  const has3 = Boolean(meta.pages["3"]);
  const now = pct(meta.coverage);
  const all = targets ? pct(targets.all_pages) : 99;

  if (!has2) {
    return (
      <p className="coverage" aria-live="polite">
        বাংলা লিখতে পাতা ২ দিন।
        <span className="en-sub" lang="en">
          Add page 2 to write Bangla.
        </span>
      </p>
    );
  }
  return (
    <p className="coverage" aria-live="polite">
      আপনার ফন্ট বাস্তব বাংলা লেখার <strong>{bnNum(now)}%</strong> ঠিকভাবে দেখায়।
      {!has3 && ` পাতা ৩ দিলে হবে প্রায় ${bnNum(all)}%।`}
      <span className="en-sub" lang="en">
        Your font covers {now}% of real Bangla text.{!has3 && ` Fill page 3 to reach ${all}%.`}
      </span>
    </p>
  );
}
