// Drawn strokes: points in mm inside the cell box (origin top-left, y down).
// What the canvas shows is what the server builds: the same quadratic curves
// through the midpoints of the points (backend/app/strokes.py, smooth()).

export type Point = [number, number];
export type Stroke = Point[];

// Minimum distance between kept points. A finger is less precise than a
// stylus, so its tiny wobbles are dropped sooner.
export const MIN_STEP_MM: Record<string, number> = { touch: 0.35, pen: 0.18, mouse: 0.25 };

export function addPoint(stroke: Stroke, p: Point, pointerType: string): boolean {
  const last = stroke[stroke.length - 1];
  const step = MIN_STEP_MM[pointerType] ?? 0.25;
  if (last && Math.hypot(p[0] - last[0], p[1] - last[1]) < step) return false;
  stroke.push([Math.round(p[0] * 1000) / 1000, Math.round(p[1] * 1000) / 1000]);
  return true;
}

/** SVG path of a stroke's centre line, in mm. */
export function strokePath(s: Stroke): string {
  if (s.length === 0) return "";
  const f = (v: number) => v.toFixed(3);
  if (s.length < 3) return `M${f(s[0][0])} ${f(s[0][1])}` + s.map((p) => `L${f(p[0])} ${f(p[1])}`).join("");
  const mid = (a: Point, b: Point): Point => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  let d = `M${f(s[0][0])} ${f(s[0][1])}`;
  let m = mid(s[0], s[1]);
  d += `L${f(m[0])} ${f(m[1])}`;
  for (let i = 1; i < s.length - 1; i++) {
    m = mid(s[i], s[i + 1]);
    d += `Q${f(s[i][0])} ${f(s[i][1])} ${f(m[0])} ${f(m[1])}`;
  }
  const end = s[s.length - 1];
  return d + `L${f(end[0])} ${f(end[1])}`;
}
