/**
 * Undulating graphene (hexagonal) lattice background.
 * Waves emanate from the cursor when it is over the visible lattice.
 */
(function () {
  function startGrapheneLattice(canvas) {
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let w = 0;
    let h = 0;
    let dpr = 1;
    let raf = 0;
    const t0 = performance.now();

    // Pointer state (screen space)
    let mx = 0;
    let my = 0;
    let pointerActive = false;
    // Smoothed epicenter so motion eases when entering/leaving lattice
    let epicX = 0;
    let epicY = 0;
    let epicStrength = 0;

    // Graphene-like honeycomb spacing
    const size = 20;
    const hexW = Math.sqrt(3) * size;
    const hexH = 2 * size;
    const vertStep = hexH * 0.75;

    // Diagonal orientation of the sheet
    const tilt = (-32 * Math.PI) / 180;
    const cosT = Math.cos(tilt);
    const sinT = Math.sin(tilt);

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (!pointerActive) {
        mx = w * 0.65;
        my = h * 0.55;
        epicX = mx;
        epicY = my;
      }
    }

    function visibilityAt(sx, sy) {
      const nx = sx / Math.max(w, 1);
      const ny = sy / Math.max(h, 1);
      // Diagonal reveal: plain white near TL, lattice denser toward BR
      const diag = nx * 0.55 + ny * 0.45;
      let v = (diag - 0.2) / 0.5;
      v = Math.max(0, Math.min(1, v));
      v = v * v * (3 - 2 * v);
      // Extra clear lobe for logo
      const logo = Math.hypot(nx / 0.42, ny / 0.32);
      if (logo < 1) {
        v *= Math.max(0, (logo - 0.15) / 0.85);
      }
      return v;
    }

    function ambientWaveOffset(x, y, time) {
      const phase = x * 0.013 + y * 0.01 + time * 1.45;
      const phase2 = x * -0.008 + y * 0.015 + time * 0.95;
      const amp = 6.2;
      return {
        dx: Math.sin(phase) * amp * 0.5 + Math.cos(phase2) * amp * 0.22,
        dy: Math.cos(phase) * amp + Math.sin(phase2) * amp * 0.32,
      };
    }

    function hexCorners(cx, cy) {
      const pts = [];
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 180) * (60 * i - 30);
        pts.push({ x: cx + size * Math.cos(a), y: cy + size * Math.sin(a) });
      }
      return pts;
    }

    function worldToScreen(x, y) {
      const rx = x * cosT - y * sinT;
      const ry = x * sinT + y * cosT;
      return {
        x: rx + w * 0.48,
        y: ry + h * 0.02,
      };
    }

    function displace(pt, time) {
      // Ambient drift always present (weaker when cursor is driving)
      const ambient = ambientWaveOffset(pt.x, pt.y, time);
      const ambScale = 1 - epicStrength * 0.65;
      let screen = worldToScreen(
        pt.x + ambient.dx * ambScale,
        pt.y + ambient.dy * ambScale
      );

      // Radial ripples from cursor epicenter when over the lattice
      if (epicStrength > 0.02) {
        const dx = screen.x - epicX;
        const dy = screen.y - epicY;
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.0001;
        // Outward traveling rings
        const phase = dist * 0.05 - time * 5.2;
        const falloff = Math.exp(-dist / 200);
        const amp = 11 * falloff * epicStrength;
        const radial = Math.sin(phase) * amp;
        // Slight secondary ring for richer water feel
        const phase2 = dist * 0.09 - time * 3.4;
        const radial2 = Math.sin(phase2) * amp * 0.35;
        const push = radial + radial2;
        screen.x += (dx / dist) * push;
        screen.y += (dy / dist) * push;
      }

      return screen;
    }

    function onPointerMove(e) {
      mx = e.clientX;
      my = e.clientY;
      // Only treat as "over lattice" when the field is actually visible there
      pointerActive = visibilityAt(mx, my) > 0.06;
    }

    function onPointerLeave() {
      pointerActive = false;
    }

    function draw(now) {
      const time = (now - t0) / 1000;
      ctx.clearRect(0, 0, w, h);

      // Ease epicenter toward cursor (or fade strength when off-lattice)
      const targetStrength = pointerActive ? 1 : 0;
      epicStrength += (targetStrength - epicStrength) * 0.12;
      if (pointerActive) {
        epicX += (mx - epicX) * 0.22;
        epicY += (my - epicY) * 0.22;
      }

      const span = Math.hypot(w, h) * 1.4;
      const cols = Math.ceil(span / hexW) + 6;
      const rows = Math.ceil(span / vertStep) + 6;
      const originX = -span * 0.55;
      const originY = -span * 0.2;

      ctx.lineWidth = Math.max(0.7, 0.85 / dpr);
      ctx.lineJoin = "round";
      ctx.lineCap = "round";

      for (let row = 0; row < rows; row++) {
        const y0 = originY + row * vertStep;
        const xOff = (row % 2) * (hexW * 0.5);
        for (let col = 0; col < cols; col++) {
          const x0 = originX + col * hexW + xOff;
          const center = worldToScreen(x0, y0);
          if (
            center.x < -100 ||
            center.y < -100 ||
            center.x > w + 100 ||
            center.y > h + 100
          ) {
            continue;
          }

          const corners = hexCorners(x0, y0);
          for (let e = 0; e < 3; e++) {
            const a = corners[e];
            const b = corners[(e + 1) % 6];
            const sa = displace(a, time);
            const sb = displace(b, time);
            const vis = (visibilityAt(sa.x, sa.y) + visibilityAt(sb.x, sb.y)) * 0.5;
            if (vis < 0.03) continue;

            const alpha = 0.08 + vis * 0.32;
            ctx.strokeStyle = "rgba(150, 90, 95, " + alpha + ")";
            ctx.beginPath();
            ctx.moveTo(sa.x, sa.y);
            ctx.lineTo(sb.x, sb.y);
            ctx.stroke();
          }
        }
      }

      // Guarantee plain white top-left (logo corner)
      const radial = ctx.createRadialGradient(0, 0, 0, 0, 0, Math.max(w, h) * 0.5);
      radial.addColorStop(0, "rgba(255,255,255,1)");
      radial.addColorStop(0.4, "rgba(255,255,255,0.95)");
      radial.addColorStop(0.62, "rgba(255,255,255,0.25)");
      radial.addColorStop(0.8, "rgba(255,255,255,0)");
      ctx.fillStyle = radial;
      ctx.fillRect(0, 0, w * 0.6, h * 0.55);

      const wipe = ctx.createLinearGradient(0, 0, w * 0.7, h * 0.7);
      wipe.addColorStop(0, "rgba(255,255,255,1)");
      wipe.addColorStop(0.18, "rgba(255,255,255,0.88)");
      wipe.addColorStop(0.4, "rgba(255,255,255,0.2)");
      wipe.addColorStop(0.58, "rgba(255,255,255,0)");
      ctx.fillStyle = wipe;
      ctx.fillRect(0, 0, w, h);

      raf = requestAnimationFrame(draw);
    }

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("pointerleave", onPointerLeave);
    document.addEventListener("pointerleave", onPointerLeave);
    raf = requestAnimationFrame(draw);

    return function stop() {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerleave", onPointerLeave);
      document.removeEventListener("pointerleave", onPointerLeave);
    };
  }

  window.MotionBotLattice = { start: startGrapheneLattice };
})();
