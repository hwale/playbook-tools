import { useEffect, useRef } from "react";

// ── Math helpers ─────────────────────────────────────────────────────────────

function cubicBezier(t: number, p0: number, p1: number, p2: number, p3: number): number {
  const u = 1 - t;
  return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3;
}

/** Clamp alpha 0–1 → two-char hex string for 8-digit CSS colors (#rrggbbaa). */
function aa(alpha: number): string {
  return Math.round(Math.max(0, Math.min(1, alpha)) * 255)
    .toString(16)
    .padStart(2, "0");
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface Node {
  x: number;
  y: number;
  color: string;
  label: string;
}

interface BezierPath {
  x0: number; y0: number;
  cx1: number; cy1: number;
  cx2: number; cy2: number;
  x3: number; y3: number;
}

interface Particle extends BezierPath {
  t: number;
  speed: number;
  r: number;
  color: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AgentFlowAnimation() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;

    const W = 540;
    const H = 210;

    // Nodes
    const DOC: Node = { x: 72,  y: 72,  color: "#818cf8", label: "Your Document" };
    const WEB: Node = { x: 72,  y: 162, color: "#22d3ee", label: "The Web"        };
    const AI:  Node = { x: 290, y: 117, color: "#f59e0b", label: "AI Agent"       };
    const ANS: Node = { x: 468, y: 117, color: "#4ade80", label: "Answer"         };

    // Static bezier paths (the visual "rails")
    const PATH_DOC: BezierPath = { x0: 72,  y0: 72,  cx1: 165, cy1: 48,  cx2: 220, cy2: 100, x3: 290, y3: 117 };
    const PATH_WEB: BezierPath = { x0: 72,  y0: 162, cx1: 165, cy1: 186, cx2: 220, cy2: 134, x3: 290, y3: 117 };
    const PATH_ANS: BezierPath = { x0: 290, y0: 117, cx1: 352, cy1: 88,  cx2: 410, cy2: 88,  x3: 468, y3: 117 };

    const particles: Particle[] = [];

    function spawn(path: BezierPath, color: string) {
      const j = () => (Math.random() - 0.5) * 22;
      particles.push({
        ...path,
        cx1: path.cx1 + j(), cy1: path.cy1 + j(),
        cx2: path.cx2 + j(), cy2: path.cy2 + j(),
        t: 0,
        speed: 0.005 + Math.random() * 0.006,
        r: 2 + Math.random() * 1.8,
        color,
      });
    }

    // Draw a node: outer glow → ring → filled core → label
    function drawNode(n: Node, extraGlow = 0) {
      // Soft outer glow
      const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, 34 + extraGlow);
      g.addColorStop(0,   n.color + "55");
      g.addColorStop(0.5, n.color + "1a");
      g.addColorStop(1,   n.color + "00");
      ctx.beginPath();
      ctx.arc(n.x, n.y, 34 + extraGlow, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();

      // Outer ring
      ctx.beginPath();
      ctx.arc(n.x, n.y, 17, 0, Math.PI * 2);
      ctx.strokeStyle = n.color + "44";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Core
      ctx.beginPath();
      ctx.arc(n.x, n.y, 12, 0, Math.PI * 2);
      ctx.fillStyle = n.color + "cc";
      ctx.fill();
      ctx.strokeStyle = n.color + "ee";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Label
      ctx.font = "9.5px ui-sans-serif, system-ui, -apple-system, sans-serif";
      ctx.fillStyle = n.color + "bb";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(n.label, n.x, n.y + 23);
    }

    // Draw the bezier "rail" path
    function drawRail(p: BezierPath, color: string) {
      ctx.save();
      ctx.strokeStyle = color + "1e";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([3, 9]);
      ctx.beginPath();
      ctx.moveTo(p.x0, p.y0);
      ctx.bezierCurveTo(p.cx1, p.cy1, p.cx2, p.cy2, p.x3, p.y3);
      ctx.stroke();
      ctx.restore();
    }

    let frame = 0;
    let pulse = 0;
    let rafId: number;

    function tick() {
      frame++;
      pulse += 0.032;

      // Staggered particle spawning
      if (frame % 22 === 0)  spawn(PATH_DOC, DOC.color);
      if (frame % 30 === 0)  spawn(PATH_WEB, WEB.color);
      if (frame % 48 === 0)  spawn(PATH_ANS, ANS.color);
      // Extra burst every few seconds to keep it lively
      if (frame % 80 === 0) { spawn(PATH_DOC, DOC.color); spawn(PATH_WEB, WEB.color); }

      // ── Background ───────────────────────────────────────────────────────────
      ctx.fillStyle = "#0d0d1c";
      ctx.fillRect(0, 0, W, H);

      // Dot grid
      ctx.fillStyle = "#ffffff09";
      for (let gx = 24; gx < W; gx += 24) {
        for (let gy = 24; gy < H; gy += 24) {
          ctx.beginPath();
          ctx.arc(gx, gy, 0.65, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // ── Rails ─────────────────────────────────────────────────────────────────
      drawRail(PATH_DOC, DOC.color);
      drawRail(PATH_WEB, WEB.color);
      drawRail(PATH_ANS, ANS.color);

      // ── Orbiting electrons around AI ─────────────────────────────────────────
      for (let i = 0; i < 3; i++) {
        const angle = pulse * 1.7 + (i * Math.PI * 2) / 3;
        // Elliptical orbit: wider horizontally
        const ox = AI.x + Math.cos(angle) * 26;
        const oy = AI.y + Math.sin(angle) * 13;

        // Trail halo
        ctx.beginPath();
        ctx.arc(ox, oy, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = AI.color + "20";
        ctx.fill();
        // Core dot
        ctx.beginPath();
        ctx.arc(ox, oy, 1.8, 0, Math.PI * 2);
        ctx.fillStyle = AI.color + "cc";
        ctx.fill();
      }

      // ── Nodes ─────────────────────────────────────────────────────────────────
      drawNode(DOC);
      drawNode(WEB);
      drawNode(AI,  Math.sin(pulse) * 8);          // AI breathes
      drawNode(ANS, Math.sin(pulse * 0.75 + 1) * 3);

      // ── Particles ─────────────────────────────────────────────────────────────
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.t += p.speed;
        if (p.t >= 1) { particles.splice(i, 1); continue; }

        const x = cubicBezier(p.t, p.x0, p.cx1, p.cx2, p.x3);
        const y = cubicBezier(p.t, p.y0, p.cy1, p.cy2, p.y3);

        // Fade in / fade out
        const a = p.t < 0.1 ? p.t / 0.1 : p.t > 0.82 ? (1 - p.t) / 0.18 : 1;

        // Outer glow (3 layers for softness)
        ctx.beginPath();
        ctx.arc(x, y, p.r + 5, 0, Math.PI * 2);
        ctx.fillStyle = p.color + aa(a * 0.12);
        ctx.fill();

        ctx.beginPath();
        ctx.arc(x, y, p.r + 2, 0, Math.PI * 2);
        ctx.fillStyle = p.color + aa(a * 0.35);
        ctx.fill();

        // Core
        ctx.beginPath();
        ctx.arc(x, y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = p.color + aa(a);
        ctx.fill();
      }

      rafId = requestAnimationFrame(tick);
    }

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, []);

  return (
    <div className="w-full max-w-lg" style={{ aspectRatio: "540/210" }}>
      <canvas
        ref={canvasRef}
        width={540}
        height={210}
        className="w-full h-full rounded-2xl"
        style={{ boxShadow: "0 0 0 1px rgba(255,255,255,0.06), 0 8px 32px rgba(0,0,0,0.4)" }}
      />
    </div>
  );
}
