import type { Mode } from "@/lib/drawstore";

// The two ways in, side by side, drawing first. Both make the same font and
// can be mixed: a letter drawn and photographed keeps the newer one.
export function ModeChoice({ mode, onMode }: { mode: Mode | null; onMode: (m: Mode) => void }) {
  // Once chosen, one line: the drawing (or the paper steps) comes right after.
  if (mode) {
    const other: Mode = mode === "draw" ? "paper" : "draw";
    return (
      <p className="mode-chosen">
        {mode === "draw" ? "আঁকছেন" : "কাগজে লিখছেন"}
        <span className="en"> · {mode === "draw" ? "drawing" : "on paper"}</span>
        <button type="button" className="button" onClick={() => onMode(other)}>
          {other === "draw" ? "আঁকুন" : "কাগজে লিখুন"} <span className="en">· {other === "draw" ? "draw instead" : "use paper instead"}</span>
        </button>
      </p>
    );
  }
  return (
    <div className="modes">
      <div className={`mode${mode === "draw" ? " chosen" : ""}`}>
        <h3>
          আঁকুন
          <span className="en-sub" lang="en">
            Draw
          </span>
        </h3>
        <p>
          ফোনে বা কম্পিউটারে, একটা একটা করে অক্ষর আঁকুন। প্রিন্টার লাগবে না; স্টাইলাস থাকলে সবচেয়ে ভালো।
          <span className="en-sub" lang="en">
            One letter at a time, on your phone or computer. No printer needed; best with a stylus.
          </span>
        </p>
        <button type="button" className={`button${mode === "draw" ? " primary" : ""}`} aria-pressed={mode === "draw"} onClick={() => onMode("draw")}>
          আঁকুন <span className="en">· draw</span>
        </button>
      </div>
      <div className={`mode${mode === "paper" ? " chosen" : ""}`}>
        <h3>
          কাগজে লিখুন
          <span className="en-sub" lang="en">
            Write on paper
          </span>
        </h3>
        <p>
          টেমপ্লেট ছেপে কলমে লিখুন, তারপর ছবি তুলুন। আপনার আসল কলমের হাতের লেখা।
          <span className="en-sub" lang="en">
            Print the template, write with your pen, photograph it. Your real pen handwriting.
          </span>
        </p>
        <button type="button" className={`button${mode === "paper" ? " primary" : ""}`} aria-pressed={mode === "paper"} onClick={() => onMode("paper")}>
          কাগজে <span className="en">· paper</span>
        </button>
      </div>
      <p className="modes-note">
        দুটো মেশানো যায়: কাগজে বাদ পড়া অক্ষর পরে এঁকে নিন।
        <span className="en-sub" lang="en">
          You can mix them: draw the letters you skipped on paper, for example.
        </span>
      </p>
    </div>
  );
}
