"use client";

import { useEffect, useRef } from "react";

type InteractiveDotGridProps = { className?: string };

const spacing = 18;
const cursorRadius = 180;

/** A full-viewport, ambient dot field that gently trails the pointer. */
export default function InteractiveDotGrid({ className }: InteractiveDotGridProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;

    let width = 0;
    let height = 0;
    let frame = 0;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pointer = { x: -cursorRadius, y: -cursorRadius, targetX: -cursorRadius, targetY: -cursorRadius, strength: 0, targetStrength: 0 };

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      width = bounds.width;
      height = bounds.height;
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * pixelRatio);
      canvas.height = Math.round(height * pixelRatio);
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    };

    const draw = (time: number) => {
      frame = 0;
      pointer.x += (pointer.targetX - pointer.x) * 0.035;
      pointer.y += (pointer.targetY - pointer.y) * 0.035;
      pointer.strength += (pointer.targetStrength - pointer.strength) * 0.04;
      context.clearRect(0, 0, width, height);

      const seconds = time / 1000;
      for (let y = spacing / 2; y < height; y += spacing) {
        for (let x = spacing / 2; x < width; x += spacing) {
          const dx = x - pointer.x;
          const dy = y - pointer.y;
          const distance = Math.hypot(dx, dy);
          const hover = Math.max(0, 1 - distance / cursorRadius) * pointer.strength;
          const ambient = reduceMotion ? 0 : Math.sin(seconds * 1.15 + x * 0.025 + y * 0.018) * 0.65;
          const driftX = reduceMotion ? 0 : Math.sin(seconds * 0.7 + y * 0.035) * 0.7;
          const driftY = reduceMotion ? 0 : Math.cos(seconds * 0.62 + x * 0.03) * 0.7;
          const push = hover * hover * 16;
          const radius = 0.72 + ambient * 0.1 + hover * 1.45;

          context.beginPath();
          context.arc(x + driftX + (distance ? (dx / distance) * push : 0), y + driftY + (distance ? (dy / distance) * push : 0), radius, 0, Math.PI * 2);
          context.fillStyle = `rgba(146, 160, 255, ${0.18 + ambient * 0.035 + hover * 0.7})`;
          context.fill();
        }
      }

      if (!reduceMotion) frame = window.requestAnimationFrame(draw);
    };

    const movePointer = (event: PointerEvent) => {
      const bounds = canvas.getBoundingClientRect();
      pointer.targetX = event.clientX - bounds.left;
      pointer.targetY = event.clientY - bounds.top;
      pointer.targetStrength = pointer.targetX >= 0 && pointer.targetY >= 0 && pointer.targetX <= width && pointer.targetY <= height ? 1 : 0;
      if (reduceMotion && !frame) frame = window.requestAnimationFrame(draw);
    };
    const clearPointer = () => { pointer.targetStrength = 0; };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    window.addEventListener("pointermove", movePointer, { passive: true });
    window.addEventListener("blur", clearPointer);
    resize();
    frame = window.requestAnimationFrame(draw);

    return () => {
      observer.disconnect();
      window.removeEventListener("pointermove", movePointer);
      window.removeEventListener("blur", clearPointer);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" style={{ position: "fixed", zIndex: -1, top: 0, right: 0, bottom: 0, left: 0, width: "100vw", height: "100dvh", pointerEvents: "none" }} />;
}
