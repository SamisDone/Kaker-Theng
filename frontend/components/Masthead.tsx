// The name, and the one signature moment: once the font exists, the name
// re-renders in the visitor's own handwriting.
export function Masthead({ userFont }: { userFont: string | null }) {
  return (
    <header className="masthead">
      <h1
        key={userFont ?? "ui"}
        className={userFont ? "in-hand" : undefined}
        style={userFont ? { fontFamily: `"${userFont}", var(--bn)` } : undefined}
      >
        কাকের ঠ্যাং
      </h1>
      <div className="latin-name" lang="en">
        Kaker Theng
      </div>
      <p>
        <span lang="bn">আপনার হাতের লেখা থেকে বাংলা আর ইংরেজি ফন্ট।</span>
        <span className="en-sub" lang="en">
          A Bangla and English font from your handwriting.
        </span>
      </p>
    </header>
  );
}
