"use client";

import { ExampleCell } from "@/components/DrawCanvas";
import { Icon } from "@/components/Icons";
import { TopBar } from "@/components/TopBar";
import type { Chapter } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import type { LayoutCell } from "@/lib/layout";
import { signName } from "@/lib/names";

// Before a chapter: what it asks for, in one screen, with one example box
// drawn the way it should be written.
export function ChapterCard(props: { chapter: Chapter; chapters: Chapter[]; example: LayoutCell; count: number; onStart: () => void; onSkip: () => void; onChapters: () => void; onFont: () => void }) {
  const { t, num } = useLang();
  const { chapter, example } = props;
  const [aboutBn, aboutEn] = chapter.about(num(props.count));
  const no = props.chapters.findIndex((c) => c.id === chapter.id) + 1;
  const sign = example.ghost ? signName(example.text, example.ghost) : null;
  return (
    <div className="screen card-screen">
      <TopBar onFont={props.onFont}>
        <button type="button" className="chapter-button" onClick={props.onChapters}>
          <span className="mono count">
            {t("অধ্যায়", "Chapter")} {num(no)}/{num(props.chapters.length)}
          </span>
          <Icon name="down" size={16} />
        </button>
      </TopBar>
      <div className="card-body">
        <h2>{t(chapter.name[0], chapter.name[1])}</h2>
        <p>{t(aboutBn, aboutEn)}</p>
        <figure className="card-example">
          <ExampleCell cell={example} />
          <figcaption>
            {t("যেমন", "For example")}: <span lang="bn">{sign ? t(sign[0], sign[1]) : example.text}</span>
          </figcaption>
        </figure>
        <div className="card-buttons">
          <button type="button" className="button big primary" onClick={props.onStart}>
            {t("শুরু করুন →", "Start →")}
          </button>
          {chapter.optional && (
            <button type="button" className="button big" onClick={props.onSkip}>
              {t("বাদ দিন", "Skip it")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
