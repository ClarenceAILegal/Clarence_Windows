/**
 * Full-page fluid undulation for the password unlock transition.
 * Solid red field becomes a waving surface, then fades toward white / main UI.
 */
(function () {
  function startLoginUndulation(canvas, options) {
    const opts = Object.assign(
      {
        durationMs: 2400,
        baseRgb: [179, 58, 58], // #b33a3a
        onComplete: null,
      },
      options || {}
    );

    const ctx = canvas.getContext("2d");
    let w = 0;
    let h = 0;
    let dpr = 1;
    let raf = 0;
    const t0 = performance.now();

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function lerp(a, b, t) {
      return a + (b - a) * t;
    }

    function easeInOut(t) {
      return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    }

    function frame(now) {
      const elapsed = now - t0;
      const progress = Math.min(1, elapsed / opts.durationMs);
      const e = easeInOut(progress);
      const time = elapsed / 1000;

      // Wave amplitude grows then softens as we fade to white
      const ampBoost = progress < 0.45 ? progress / 0.45 : 1 - (progress - 0.45) / 0.55;
      const amp = 14 + 22 * ampBoost;
      const fadeToWhite = Math.pow(Math.max(0, (progress - 0.28) / 0.72), 1.15);

      // Base color: red → soft white
      const br = lerp(opts.baseRgb[0], 255, fadeToWhite);
      const bg = lerp(opts.baseRgb[1], 255, fadeToWhite);
      const bb = lerp(opts.baseRgb[2], 255, fadeToWhite);

      ctx.fillStyle = "rgb(" + br + "," + bg + "," + bb + ")";
      ctx.fillRect(0, 0, w, h);

      // Horizontal fluid bands (full-page undulation)
      const band = 6;
      for (let y = -amp - 4; y < h + amp + 4; y += band) {
        const n1 = Math.sin(y * 0.018 + time * 2.4) * amp;
        const n2 = Math.cos(y * 0.031 - time * 1.7) * amp * 0.55;
        const n3 = Math.sin(y * 0.009 + time * 3.1) * amp * 0.35;
        const offset = n1 + n2 + n3;

        // Slight tonal shift along the wave for depth
        const shade = 0.92 + 0.08 * Math.sin(y * 0.04 + time * 2);
        const wr = Math.min(255, br * shade + 12 * (1 - fadeToWhite));
        const wg = Math.min(255, bg * shade + 8 * (1 - fadeToWhite));
        const wb = Math.min(255, bb * shade + 8 * (1 - fadeToWhite));
        const alpha = 0.22 + 0.2 * (1 - fadeToWhite);

        ctx.beginPath();
        ctx.moveTo(0, y + offset);
        for (let x = 0; x <= w; x += 24) {
          const local =
            Math.sin(x * 0.012 + y * 0.01 + time * 2.6) * amp * 0.45 +
            Math.cos(x * 0.007 - time * 1.9) * amp * 0.25;
          ctx.lineTo(x, y + offset + local);
        }
        ctx.lineTo(w, y + band + 8);
        ctx.lineTo(0, y + band + 8);
        ctx.closePath();
        ctx.fillStyle =
          "rgba(" +
          Math.round(wr) +
          "," +
          Math.round(wg) +
          "," +
          Math.round(wb) +
          "," +
          alpha +
          ")";
        ctx.fill();
      }

      // Soft sheen sweeping across
      const sheenX = (Math.sin(time * 1.2) * 0.5 + 0.5) * w;
      const grd = ctx.createRadialGradient(sheenX, h * 0.45, 10, sheenX, h * 0.45, w * 0.55);
      grd.addColorStop(0, "rgba(255,255,255," + (0.14 * (1 - fadeToWhite * 0.5)) + ")");
      grd.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = grd;
      ctx.fillRect(0, 0, w, h);

      // Global fade out at the end into white
      if (progress > 0.72) {
        const endFade = (progress - 0.72) / 0.28;
        ctx.fillStyle = "rgba(255,255,255," + endFade + ")";
        ctx.fillRect(0, 0, w, h);
      }

      if (progress < 1) {
        raf = requestAnimationFrame(frame);
      } else if (typeof opts.onComplete === "function") {
        opts.onComplete();
      }
    }

    resize();
    window.addEventListener("resize", resize);
    canvas.classList.add("active");
    raf = requestAnimationFrame(frame);

    return function stop() {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }

  window.LoginUndulate = { start: startLoginUndulation };
})();
