import { templateUrl } from "@/lib/api";
import { bnNum } from "@/lib/bn";
import type { Layout } from "@/lib/layout";

export function PrintSection({ layout }: { layout: Layout | null }) {
  // The static copy loads instantly; the backend's copy is the fallback.
  const pdf = layout ? `/kt/${layout.template_pdf}` : templateUrl();
  return (
    <section className="section" aria-labelledby="print-title">
      <div className="section-head">
        <span className="section-no">১ / 1</span>
        <h2 id="print-title">
          ছাপুন
          <span className="en-sub" lang="en">
            Print the template
          </span>
        </h2>
      </div>
      <p>
        তিনটে পাতা। ১০০% মাপে ছাপুন, রঙিন বা সাদাকালো দুটোই চলবে।
        <span className="en-sub" lang="en">
          Three A4 pages. Print at 100% (actual size), in colour or black and white.
        </span>
      </p>
      <p>
        <a className="button" href={pdf} target="_blank" rel="noopener">
          টেমপ্লেট (PDF) <span className="en">· template</span>
        </a>
      </p>
      <div className="thumbs">
        {[1, 2, 3].map((n) => {
          const page = layout?.pages[n];
          return (
            <figure key={n}>
              <a href={pdf} target="_blank" rel="noopener">
                <img
                  src={`/kt/template-p${n}.png`}
                  width={128}
                  height={181}
                  alt={`টেমপ্লেটের পাতা ${bnNum(n)}${page ? `: ${page.title_bn}` : ""}. Template page ${n}${page ? `: ${page.title_en}` : ""}.`}
                />
              </a>
              <figcaption>
                p{n}
                {page?.optional ? " · optional" : ""}
              </figcaption>
            </figure>
          );
        })}
      </div>
      <p>
        পাতা ১ আর ২ দিলেই ফন্ট চলবে। পাতা ৩ ঐচ্ছিক: যুক্তবর্ণ আরও ভালো হয়।
        <span className="en-sub" lang="en">
          Pages 1 and 2 make a working font. Page 3 is optional: it makes conjuncts better.
        </span>
      </p>
    </section>
  );
}
