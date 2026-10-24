const DIGITS = "০১২৩৪৫৬৭৮৯";

export function bnNum(n: number | string): string {
  return String(n).replace(/[0-9]/g, (d) => DIGITS[Number(d)]);
}

/** "about 40 s left" from the server's estimate: rounded up to 10 s under a
 *  minute, whole minutes above. Null when there is no useful estimate. */
export function timeLeft(seconds: number | null | undefined): [string, string] | null {
  if (seconds == null || seconds < 5) return null;
  if (seconds < 60) {
    const s = Math.ceil(seconds / 10) * 10;
    return [`প্রায় ${bnNum(s)} সেকেন্ড বাকি`, `about ${s} s left`];
  }
  const m = Math.ceil(seconds / 60);
  return [`প্রায় ${bnNum(m)} মিনিট বাকি`, `about ${m} min left`];
}

export function pct(x: number): number {
  return Math.round(x * 100);
}

const CORNER_BN: Record<string, string> = {
  "top-left": "উপরে বাঁয়ের",
  "top-right": "উপরে ডানের",
  "bottom-right": "নিচে ডানের",
  "bottom-left": "নিচে বাঁয়ের",
};

export function cornerBn(c: string) {
  return CORNER_BN[c] ?? c;
}
