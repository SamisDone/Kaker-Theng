"use client";

import { useEffect, useRef } from "react";
import type { LayoutCell } from "@/lib/layout";
import { addPoint, type Stroke, strokePath } from "@/lib/strokes";

const PAPER = "#f4f0e6";
const RULE = "#b9c6e0";
const GHOST = "rgba(29, 33, 64, 0.16)";
const INK = "#1d2140";

// One letter's box, drawn like the template cell: border, baseline and
// মাত্রা line (dashed x-height for English), the faint ghost letter, and the
// user's strokes. Pointer events cover finger, stylus and mouse alike.
export function DrawCanvas(props: {
  cell: LayoutCell;
  strokes: Stroke[];
  penMm: number;
  maxHeight: number; // css px the canvas may take; it is as large as this and its column allow
  onStroke: (s: Stroke) => void;
  onActivity?: () => void; // a stroke started or ended
}) {
  const { cell, strokes, penMm, maxHeight, onStroke } = props;
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const live = useRef<{ id: number; type: string; stroke: Stroke } | null>(null);
  const frame = useRef(0);
  const g = cell.draw;

  const paint = () => {
    const c = canvas.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const k = c.width / g.w; // device px per mm
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = PAPER;
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.setTransform(k, 0, 0, k, 0, 0);

    ctx.lineWidth = 0.12;
    ctx.strokeStyle = RULE;
    ctx.strokeRect(0.06, 0.06, g.w - 0.12, g.h - 0.12);
    const guide = (y: number, dashed = false) => {
      ctx.setLineDash(dashed ? [0.6, 0.6] : []);
      ctx.beginPath();
      ctx.moveTo(g.inset, y);
      ctx.lineTo(g.w - g.inset, y);
      ctx.stroke();
    };
    ctx.lineWidth = 0.18;
    guide(g.base);
    guide(g.head);
    if (g.xh !== undefined) guide(g.xh, true);
    ctx.setLineDash([]);

    if (g.ghost) {
      ctx.fillStyle = GHOST;
      ctx.fill(new Path2D(g.ghost));
    }

    ctx.strokeStyle = INK;
    ctx.lineWidth = penMm;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const all = live.current ? [...strokes, live.current.stroke] : strokes;
    for (const s of all) {
      if (s.length === 1) {
        ctx.fillStyle = INK;
        ctx.beginPath();
        ctx.arc(s[0][0], s[0][1], penMm / 2, 0, 2 * Math.PI);
        ctx.fill();
      } else if (s.length > 1) {
        ctx.stroke(new Path2D(strokePath(s)));
      }
    }
  };

  // Size the canvas to its box at the screen's pixel density.
  useEffect(() => {
    const el = wrap.current;
    const c = canvas.current;
    if (!el || !c) return;
    const fit = () => {
      const cssW = Math.max(160, Math.min(el.clientWidth, (maxHeight * g.w) / g.h));
      const dpr = window.devicePixelRatio || 1;
      c.style.width = `${cssW}px`;
      c.style.height = `${(cssW * g.h) / g.w}px`;
      c.width = Math.round(cssW * dpr);
      c.height = Math.round((cssW * g.h * dpr) / g.w);
      paint();
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [g.w, g.h, maxHeight]);

  // The page must never scroll or zoom under a drawing finger. touch-action
  // (CSS) does it in current browsers; these listeners cover older ones.
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const stop = (e: TouchEvent) => e.preventDefault();
    c.addEventListener("touchstart", stop, { passive: false });
    c.addEventListener("touchmove", stop, { passive: false });
    return () => {
      c.removeEventListener("touchstart", stop);
      c.removeEventListener("touchmove", stop);
    };
  }, []);

  useEffect(paint);

  const toMm = (e: { clientX: number; clientY: number }): [number, number] => {
    const r = canvas.current!.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * g.w;
    const y = ((e.clientY - r.top) / r.height) * g.h;
    // A stroke that wanders off the box is kept at its edge.
    return [Math.min(g.w, Math.max(0, x)), Math.min(g.h, Math.max(0, y))];
  };

  const schedule = () => {
    if (!frame.current) frame.current = requestAnimationFrame(() => ((frame.current = 0), paint()));
  };

  return (
    <div className="draw-canvas" ref={wrap}>
      <canvas
        ref={canvas}
        role="img"
        aria-label={`আঁকার ঘর: ${cell.text}. Drawing box for ${cell.text}.`}
        onPointerDown={(e) => {
          e.preventDefault();
          if (live.current || (e.pointerType === "mouse" && e.button !== 0)) return;
          props.onActivity?.();
          e.currentTarget.setPointerCapture(e.pointerId);
          const stroke: Stroke = [];
          addPoint(stroke, toMm(e), e.pointerType);
          live.current = { id: e.pointerId, type: e.pointerType, stroke };
          schedule();
        }}
        onPointerMove={(e) => {
          e.preventDefault();
          const l = live.current;
          if (!l || l.id !== e.pointerId) return;
          const events = e.nativeEvent.getCoalescedEvents?.() ?? [e.nativeEvent];
          let added = false;
          for (const ev of events.length ? events : [e.nativeEvent]) added = addPoint(l.stroke, toMm(ev), l.type) || added;
          if (added) schedule();
        }}
        onPointerUp={(e) => {
          const l = live.current;
          if (!l || l.id !== e.pointerId) return;
          e.preventDefault();
          addPoint(l.stroke, toMm(e), l.type);
          live.current = null;
          onStroke(l.stroke);
          props.onActivity?.();
        }}
        onPointerCancel={(e) => {
          if (live.current?.id === e.pointerId) {
            live.current = null;
            schedule();
          }
        }}
      />
    </div>
  );
}

// A small view of a drawn letter for the neighbours strip. Every cell in the
// strip uses the same frame (mm above and below the baseline), so they share
// one scale and their baselines line up whatever their height.
export function MiniCell({ cell, strokes, penMm, above, below, current }: { cell: LayoutCell; strokes: Stroke[]; penMm: number; above: number; below: number; current: boolean }) {
  const g = cell.draw;
  return (
    <svg className={`mini-cell${current ? " current" : ""}`} viewBox={`0 ${g.base - above} ${g.w} ${above + below}`} aria-hidden="true">
      <rect x={0.15} y={0.15} width={g.w - 0.3} height={g.h - 0.3} fill="none" stroke={current ? INK : RULE} strokeWidth={current ? 0.5 : 0.3} />
      <line x1={g.inset} x2={g.w - g.inset} y1={g.base} y2={g.base} stroke={RULE} strokeWidth={0.25} />
      <line x1={g.inset} x2={g.w - g.inset} y1={g.head} y2={g.head} stroke={RULE} strokeWidth={0.25} />
      {g.ghost && <path d={g.ghost} fill={GHOST} />}
      {strokes.map((s, i) =>
        s.length === 1 ? (
          <circle key={i} cx={s[0][0]} cy={s[0][1]} r={penMm / 2} fill={INK} />
        ) : (
          <path key={i} d={strokePath(s)} fill="none" stroke={INK} strokeWidth={penMm} strokeLinecap="round" strokeLinejoin="round" />
        ),
      )}
    </svg>
  );
}
