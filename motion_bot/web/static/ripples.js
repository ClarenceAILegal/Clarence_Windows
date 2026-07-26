/* Canvas water-ripple effects for login transition + futuristic ambient page */

(function () {
  function createRippleEngine(canvas, options) {
    const opts = Object.assign(
      {
        interactive: false,
        ambient: false,
        baseColor: [0, 0, 128],
        waveColor: [180, 220, 255],
        clearAlpha: 0.08,
      },
      options || {}
    );

    const ctx = canvas.getContext("2d");
    let width = 0;
    let height = 0;
    let ripples = [];
    let raf = null;
    let running = false;

    function resize() {
      width = canvas.width = window.innerWidth * devicePixelRatio;
      height = canvas.height = window.innerHeight * devicePixelRatio;
      canvas.style.width = window.innerWidth + "px";
      canvas.style.height = window.innerHeight + "px";
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    }

    function addRipple(x, y, force) {
      ripples.push({
        x: x,
        y: y,
        radius: 2,
        max: Math.max(window.innerWidth, window.innerHeight) * (force || 1.1),
        line: 3.5 * (force || 1),
        alpha: 0.85,
        decay: 0.012 + Math.random() * 0.008,
        speed: 3.2 + Math.random() * 2.4,
      });
      // secondary quieter rings
      ripples.push({
        x: x,
        y: y,
        radius: 1,
        max: Math.max(window.innerWidth, window.innerHeight) * 0.7 * (force || 1),
        line: 2,
        alpha: 0.45,
        decay: 0.01,
        speed: 2.2,
        delay: 8,
      });
      ripples.push({
        x: x,
        y: y,
        radius: 1,
        max: Math.max(window.innerWidth, window.innerHeight) * 0.45 * (force || 1),
        line: 1.4,
        alpha: 0.3,
        decay: 0.009,
        speed: 1.6,
        delay: 18,
      });
    }

    function frame() {
      if (!running) return;
      const w = window.innerWidth;
      const h = window.innerHeight;

      if (opts.ambient) {
        ctx.fillStyle = "rgba(255,255,255," + opts.clearAlpha + ")";
        ctx.fillRect(0, 0, w, h);
      } else {
        ctx.clearRect(0, 0, w, h);
      }

      ripples = ripples.filter(function (r) {
        if (r.delay && r.delay > 0) {
          r.delay -= 1;
          return true;
        }
        r.radius += r.speed;
        r.alpha -= r.decay;
        r.line *= 0.992;
        if (r.alpha <= 0.02 || r.radius > r.max) return false;

        ctx.beginPath();
        ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
        ctx.strokeStyle =
          "rgba(" +
          opts.waveColor[0] +
          "," +
          opts.waveColor[1] +
          "," +
          opts.waveColor[2] +
          "," +
          r.alpha +
          ")";
        ctx.lineWidth = Math.max(0.6, r.line);
        ctx.stroke();

        // soft outer glow ring
        ctx.beginPath();
        ctx.arc(r.x, r.y, r.radius * 0.92, 0, Math.PI * 2);
        ctx.strokeStyle =
          "rgba(" +
          opts.waveColor[0] +
          "," +
          opts.waveColor[1] +
          "," +
          opts.waveColor[2] +
          "," +
          r.alpha * 0.35 +
          ")";
        ctx.lineWidth = Math.max(0.4, r.line * 2.2);
        ctx.stroke();
        return true;
      });

      if (opts.ambient && Math.random() < 0.02) {
        addRipple(Math.random() * w, Math.random() * h, 0.35 + Math.random() * 0.35);
      }

      raf = requestAnimationFrame(frame);
    }

    function start() {
      if (running) return;
      running = true;
      resize();
      frame();
    }

    function stop() {
      running = false;
      if (raf) cancelAnimationFrame(raf);
    }

    function splash(x, y, force) {
      start();
      addRipple(x, y, force);
    }

    window.addEventListener("resize", resize);
    if (opts.interactive) {
      canvas.style.pointerEvents = "auto";
      window.addEventListener("pointerdown", function (e) {
        splash(e.clientX, e.clientY, 0.7);
      });
    }

    return { start: start, stop: stop, splash: splash, resize: resize };
  }

  window.MotionBotRipples = { create: createRippleEngine };
})();
