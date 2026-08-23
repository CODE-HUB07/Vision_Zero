import React, { useEffect, useRef } from "react";

export default function VisualizerCanvas({ telemetry = [], currentSpeed = 0, currentLimit = 40, riskLevel = "SAFE" }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;

    const resizeCanvas = () => {
      canvas.width = parent.clientWidth;
      canvas.height = parent.clientHeight;
    };

    const draw = () => {
      const ctx = canvas.getContext("2d");
      const width = canvas.width;
      const height = canvas.height;

      // Clear background with soft white card background (#FFFFFF)
      ctx.fillStyle = "#FFFFFF";
      ctx.fillRect(0, 0, width, height);

      // 1. Draw subtle grid lines
      ctx.strokeStyle = "rgba(107, 114, 128, 0.06)";
      ctx.lineWidth = 1;
      const gridSpacing = 24;
      for (let x = 0; x < width; x += gridSpacing) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += gridSpacing) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // 2. Generate a winding road path
      const points = [];
      const segments = 100;
      for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        const x = 40 + t * (width - 80);
        const y = height / 2 + Math.sin(t * Math.PI * 4.5) * (height * 0.22);
        points.push({ x, y });
      }

      // Draw road base
      ctx.strokeStyle = "#E4E7EB";
      ctx.lineWidth = 12;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let p of points) {
        ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();

      // Road inner path
      ctx.strokeStyle = "#F3F4F6";
      ctx.lineWidth = 8;
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let p of points) {
        ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();

      // Center dashed line
      ctx.strokeStyle = "rgba(107, 114, 128, 0.15)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let p of points) {
        ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
      ctx.setLineDash([]); // Reset

      // 3. Draw past telemetry markers
      if (telemetry.length > 0) {
        telemetry.forEach((record, index) => {
          const t = Math.min(1, index / segments);
          const pIndex = Math.min(points.length - 1, Math.floor(t * (points.length - 1)));
          const pos = points[pIndex];

          if (record.phone_use || record.phoneUse) {
            ctx.fillStyle = "#6B7280"; // Muted gray secondary for phone use
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 4, 0, Math.PI * 2);
            ctx.fill();
          } else if (record.risk_level === "HIGH_RISK" || record.riskLevel === "HIGH_RISK") {
            ctx.fillStyle = "#DC2626"; // Risk Red
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 4, 0, Math.PI * 2);
            ctx.fill();
          } else if (record.risk_level === "WARNING" || record.riskLevel === "WARNING") {
            ctx.fillStyle = "#D97706"; // Warning Amber
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 4, 0, Math.PI * 2);
            ctx.fill();
          } else {
            ctx.fillStyle = "rgba(22, 163, 74, 0.4)"; // Safe Green
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 2, 0, Math.PI * 2);
            ctx.fill();
          }
        });
      }

      // 4. Draw active vehicle position marker
      const currentProgress = telemetry.length > 0 ? (telemetry.length - 1) / segments : 0;
      const currentT = Math.min(1, currentProgress);
      const carPosIndex = Math.min(points.length - 1, Math.floor(currentT * (points.length - 1)));
      const carPos = points[carPosIndex];

      let pulseColor = "#16A34A"; // Safe Green
      if (riskLevel === "WARNING") pulseColor = "#D97706";
      else if (riskLevel === "HIGH_RISK") pulseColor = "#DC2626";

      // Precise, low-glow cursor ring
      const pulseRadius = 6 + Math.abs(Math.sin(Date.now() / 300)) * 2;
      ctx.strokeStyle = pulseColor;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(carPos.x, carPos.y, pulseRadius, 0, Math.PI * 2);
      ctx.stroke();

      // Solid center
      ctx.fillStyle = "#111827";
      ctx.beginPath();
      ctx.arc(carPos.x, carPos.y, 3, 0, Math.PI * 2);
      ctx.fill();

      // 5. HUD text overlay
      ctx.font = "bold 9px Inter";
      ctx.fillStyle = "rgba(107, 114, 128, 0.7)";
      ctx.fillText("TRAJECTORY MONITOR", 12, 18);

      ctx.font = "bold 11px Outfit";
      ctx.fillStyle = pulseColor;
      ctx.fillText(`${Math.round(currentSpeed)} KM/H / LIMIT ${currentLimit}`, 12, 32);
    };

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    let animationId;
    const animate = () => {
      draw();
      animationId = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      window.removeEventListener("resize", resizeCanvas);
      cancelAnimationFrame(animationId);
    };
  }, [telemetry, currentSpeed, currentLimit, riskLevel]);

  return (
    <div className="relative border border-safety-border rounded-md overflow-hidden w-full h-[220px] bg-safety-card">
      <canvas
        ref={canvasRef}
        className="w-full h-full block"
      />
      <div className="absolute bottom-2 right-2 px-2 py-0.5 text-[9px] bg-safety-dark/90 text-safety-textSecondary rounded uppercase font-mono font-bold tracking-widest border border-safety-border select-none">
        Telemetry Canvas
      </div>
    </div>
  );
}
