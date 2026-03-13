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

// ── Constants ─────────────────────────────────────────────────────────────────

const PLAYBOOK_NAMES = ["finance", "game-design", "general"];
// How many frames each label is "active" (60fps → 150 frames ≈ 2.5 s each)
const PLAYBOOK_HOLD = 150;
const PLAYBOOK_FADE = 25; // frames for fade-in / fade-out

// ── Component ─────────────────────────────────────────────────────────────────

export default function AgentFlowAnimation() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;

    const W = 540;
    const H = 262;

    // ── Nodes ──────────────────────────────────────────────────────────────────
    // Shifted +10px down from center so the Playbook pill has breathing room at
    // the top edge, while trimming unused space at the bottom (H reduced to 262).
    const AI:   Node = { x: 270, y: 150, color: "#f59e0b", label: "AI Agent"      };
    const BOOK: Node = { x: 270, y: 40,  color: "#a78bfa", label: "Playbook"      };
    const DOC:  Node = { x: 68,  y: 98,  color: "#f472b6", label: "Your Document" };
    const WEB:  Node = { x: 68,  y: 202, color: "#22d3ee", label: "The Web"       };
    const ANS:  Node = { x: 472, y: 150, color: "#4ade80", label: "Answer"        };

    // ── Static bezier rails ────────────────────────────────────────────────────
    // DOC/WEB arcs are mirror images — both converge to AI center.
    const PATH_DOC:  BezierPath = { x0: 68,  y0: 98,  cx1: 162, cy1: 72,  cx2: 218, cy2: 138, x3: 270, y3: 150 };
    const PATH_WEB:  BezierPath = { x0: 68,  y0: 202, cx1: 162, cy1: 228, cx2: 218, cy2: 162, x3: 270, y3: 150 };
    const PATH_ANS:  BezierPath = { x0: 270, y0: 150, cx1: 355, cy1: 122, cx2: 415, cy2: 122, x3: 472, y3: 150 };
    // Playbook → AI: vertical drop directly above
    const PATH_BOOK: BezierPath = { x0: 270, y0: 40,  cx1: 270, cy1: 80,  cx2: 270, cy2: 122, x3: 270, y3: 150 };

    const particles: Particle[] = [];

    function spawn(path: BezierPath, color: string, jitter = 22) {
      const j = () => (Math.random() - 0.5) * jitter;
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
      const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, 34 + extraGlow);
      g.addColorStop(0,   n.color + "55");
      g.addColorStop(0.5, n.color + "1a");
      g.addColorStop(1,   n.color + "00");
      ctx.beginPath();
      ctx.arc(n.x, n.y, 34 + extraGlow, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(n.x, n.y, 17, 0, Math.PI * 2);
      ctx.strokeStyle = n.color + "44";
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(n.x, n.y, 12, 0, Math.PI * 2);
      ctx.fillStyle = n.color + "cc";
      ctx.fill();
      ctx.strokeStyle = n.color + "ee";
      ctx.lineWidth = 1.5;
      ctx.stroke();

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

    // Draw the cycling playbook name pill above the BOOK node
    function drawPlaybookLabel(frame: number) {
      const cycle = frame % (PLAYBOOK_NAMES.length * PLAYBOOK_HOLD);
      const idx   = Math.floor(cycle / PLAYBOOK_HOLD);
      const pos   = cycle % PLAYBOOK_HOLD;

      // Fade in → hold → fade out
      let alpha = 1;
      if (pos < PLAYBOOK_FADE) {
        alpha = pos / PLAYBOOK_FADE;
      } else if (pos > PLAYBOOK_HOLD - PLAYBOOK_FADE) {
        alpha = (PLAYBOOK_HOLD - pos) / PLAYBOOK_FADE;
      }

      const label = PLAYBOOK_NAMES[idx];
      const lx = BOOK.x;
      const ly = BOOK.y - 16; // floats above the node

      const textW = label.length * 6.2 + 14;
      const pillH = 16;
      const pillX = lx - textW / 2;
      const pillY = ly - pillH / 2;

      ctx.save();
      ctx.globalAlpha = alpha * 0.9;

      ctx.beginPath();
      ctx.roundRect(pillX, pillY, textW, pillH, 6);
      ctx.fillStyle = BOOK.color + "28";
      ctx.fill();
      ctx.strokeStyle = BOOK.color + "55";
      ctx.lineWidth = 0.8;
      ctx.stroke();

      ctx.font = "bold 8.5px ui-monospace, monospace";
      ctx.fillStyle = BOOK.color + "ee";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, lx, ly);
      ctx.restore();
    }

    let frame = 0;
    let pulse = 0;
    let rafId: number;

    function tick() {
      frame++;
      pulse += 0.032;

      // Data-flow particles (doc + web → AI, AI → answer)
      if (frame % 22 === 0) spawn(PATH_DOC, DOC.color);
      if (frame % 30 === 0) spawn(PATH_WEB, WEB.color);
      if (frame % 48 === 0) spawn(PATH_ANS, ANS.color);
      if (frame % 80 === 0) { spawn(PATH_DOC, DOC.color); spawn(PATH_WEB, WEB.color); }

      // Playbook config particles: slower, tighter jitter, drift down to AI Agent
      if (frame % 55 === 0) spawn(PATH_BOOK, BOOK.color, 6);

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
      drawRail(PATH_DOC,  DOC.color);
      drawRail(PATH_WEB,  WEB.color);
      drawRail(PATH_ANS,  ANS.color);
      drawRail(PATH_BOOK, BOOK.color);

      // ── Orbiting electrons around AI ─────────────────────────────────────────
      for (let i = 0; i < 3; i++) {
        const angle = pulse * 1.7 + (i * Math.PI * 2) / 3;
        const ox = AI.x + Math.cos(angle) * 26;
        const oy = AI.y + Math.sin(angle) * 13;

        ctx.beginPath();
        ctx.arc(ox, oy, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = AI.color + "20";
        ctx.fill();

        ctx.beginPath();
        ctx.arc(ox, oy, 1.8, 0, Math.PI * 2);
        ctx.fillStyle = AI.color + "cc";
        ctx.fill();
      }

      // ── Nodes ─────────────────────────────────────────────────────────────────
      drawNode(DOC);
      drawNode(WEB);
      drawNode(BOOK, Math.sin(pulse * 0.6) * 4); // playbook: gentle breathe
      drawNode(AI,   Math.sin(pulse) * 8);         // AI: bigger breathe
      drawNode(ANS,  Math.sin(pulse * 0.75 + 1) * 3);

      // ── Cycling playbook name pill ─────────────────────────────────────────────
      drawPlaybookLabel(frame);

      // ── Particles ─────────────────────────────────────────────────────────────
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.t += p.speed;
        if (p.t >= 1) { particles.splice(i, 1); continue; }

        const x = cubicBezier(p.t, p.x0, p.cx1, p.cx2, p.x3);
        const y = cubicBezier(p.t, p.y0, p.cy1, p.cy2, p.y3);

        const a = p.t < 0.1 ? p.t / 0.1 : p.t > 0.82 ? (1 - p.t) / 0.18 : 1;

        ctx.beginPath();
        ctx.arc(x, y, p.r + 5, 0, Math.PI * 2);
        ctx.fillStyle = p.color + aa(a * 0.12);
        ctx.fill();

        ctx.beginPath();
        ctx.arc(x, y, p.r + 2, 0, Math.PI * 2);
        ctx.fillStyle = p.color + aa(a * 0.35);
        ctx.fill();

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
    <div className="w-full max-w-lg" style={{ aspectRatio: "540/262" }}>
      <canvas
        ref={canvasRef}
        width={540}
        height={262}
        className="w-full h-full rounded-2xl"
        style={{ boxShadow: "0 0 0 1px rgba(255,255,255,0.06), 0 8px 32px rgba(0,0,0,0.4)" }}
      />
    </div>
  );
}
