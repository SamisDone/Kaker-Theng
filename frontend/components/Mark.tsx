import { MARK_DOT, MARK_PATHS, MARK_VIEWBOX, markStroke } from "@/lib/mark";

// The logo inline, in the ink colour (currentColor) with its red dot.
// Decorative: the site's name always stands next to it. `weight`: the
// stroke on screen, px, to sit with the text beside it.
export function Mark({ height, weight, className }: { height: number; weight?: number; className?: string }) {
  const [x, y, w, h] = MARK_VIEWBOX;
  const { stroke, dot } = markStroke(height, weight);
  return (
    <svg className={className} width={Math.round((height * w) / h)} height={height} viewBox={`${x} ${y} ${w} ${h}`} aria-hidden="true" focusable="false">
      <g fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
        {MARK_PATHS.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
      <circle cx={MARK_DOT.cx} cy={MARK_DOT.cy} r={dot} fill="var(--margin)" />
    </svg>
  );
}
