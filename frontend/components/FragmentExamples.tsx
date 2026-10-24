"use client";

import { useLang } from "@/lib/i18n";
import type { Fragment } from "@/lib/layout";

// The * cells on page 3 ask for one piece of a conjunct. Each example shows
// the conjunct in Noto Sans Bengali: the faint part is printed in the cell,
// the dark part is what to write.
export function FragmentExamples({ fragments, headline }: { fragments: Fragment[]; headline: number }) {
  const { t } = useLang();
  if (!fragments.length) return null;
  return (
    <details className="examples">
      <summary>{t("পাতা ৩-এর * ঘরে কী লিখবেন", "What to write in the * boxes on page 3")}</summary>
      <p>
        {t(
          "হালকা অংশটা ঘরে ছাপা থাকে। গাঢ় অংশটা আপনি লিখবেন, যেমন সাধারণত লেখেন।",
          "The faint part is printed in the box. Write the dark part, the way you usually would.",
        )}
      </p>
      <div className="example-grid">
        {fragments.map((f) => (
          <figure className="example" key={f.id}>
            <svg viewBox={f.viewBox.join(" ")} role="img" aria-label={t(`উদাহরণ ${f.text}: শুধু গাঢ় অংশটা লিখুন।`, `Example for ${f.text}: write only the dark part.`)}>
              <line x1={f.viewBox[0]} x2={f.viewBox[0] + f.viewBox[2]} y1={0} y2={0} stroke="var(--rule)" strokeWidth={8} />
              <line x1={f.viewBox[0]} x2={f.viewBox[0] + f.viewBox[2]} y1={-headline} y2={-headline} stroke="var(--rule)" strokeWidth={8} />
              <path d={f.ghost} fill="var(--rule)" />
              <path d={f.piece} fill="var(--ink)" />
            </svg>
            <figcaption className="label">
              <span lang="bn">{f.text}</span>
            </figcaption>
          </figure>
        ))}
      </div>
    </details>
  );
}
