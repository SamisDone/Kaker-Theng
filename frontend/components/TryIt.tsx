"use client";

import { useId, useState } from "react";

const SAMPLE = "আমি প্রতিদিন সকালে চা খাই। কর্মী ক্ষমা চাইল।\nবিদ্যালয়ের সামনে বৃষ্টি পড়ছে।\nThe quick brown fox jumps over the lazy dog.";

export function TryIt({ userFont }: { userFont: string | null }) {
  const id = useId();
  const sizeId = useId();
  const [text, setText] = useState(SAMPLE);
  const [size, setSize] = useState(28);
  // Lines stay on the khata rules: the line height is a whole number of rules.
  const lineHeight = Math.ceil((size * 1.45) / 32) * 32;

  return (
    <div className="tryit">
      <label htmlFor={id}>
        <span lang="bn">লিখে দেখুন</span>
        <span className="en-sub" lang="en">
          {userFont ? "Type to try your font" : "Type here; your font shows once a page is read"}
        </span>
      </label>
      <textarea
        id={id}
        value={text}
        spellCheck={false}
        onChange={(e) => setText(e.target.value)}
        style={{
          fontFamily: userFont ? `"${userFont}", var(--bn)` : "var(--bn)",
          fontSize: size,
          lineHeight: `${lineHeight}px`,
          backgroundSize: `8px ${lineHeight}px`,
        }}
      />
      <div className="size-control">
        <label className="mono" htmlFor={sizeId}>
          size
        </label>
        <input id={sizeId} type="range" min={18} max={72} step={2} value={size} onChange={(e) => setSize(Number(e.target.value))} />
        <span className="mono" aria-hidden="true">
          {size}px
        </span>
      </div>
    </div>
  );
}
