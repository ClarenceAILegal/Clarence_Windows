/**
 * Login lattice made of Clarence angry-bear heads (same mark as the menu icon).
 * Undulates like the graphene lattice; intensity/speed ramp on unlock.
 */
(function () {
  // 32×32 icon geometry (matches menu SVG)
  var EAR_HEAD = "#f3d4b0";
  var EAR_INNER = "#e8a090";
  var SNOUT = "#f7e2c9";
  var INK = "#1c1012";

  function drawBear(ctx, cx, cy, scale, alpha, lineBoost) {
    if (alpha <= 0.02) return;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(scale, scale);
    // Icon is centered on (16, 16.5) in viewBox space
    ctx.translate(-16, -16.5);
    ctx.globalAlpha = Math.max(0, Math.min(1, alpha));

    var stroke = 1.35 * (lineBoost || 1);
    var browW = 1.55 * (lineBoost || 1);
    var mouthW = 1.35 * (lineBoost || 1);

    function circle(x, y, r, fill, strokeColor, sw) {
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
      if (strokeColor && sw) {
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = sw;
        ctx.lineJoin = "round";
        ctx.stroke();
      }
    }

    // Ears
    circle(7.5, 8.5, 4.2, EAR_HEAD, INK, stroke);
    circle(24.5, 8.5, 4.2, EAR_HEAD, INK, stroke);
    circle(7.5, 8.5, 2.1, EAR_INNER, null, 0);
    circle(24.5, 8.5, 2.1, EAR_INNER, null, 0);

    // Head
    circle(16, 17, 10.5, EAR_HEAD, INK, stroke);

    // Angry brows
    ctx.strokeStyle = INK;
    ctx.lineWidth = browW;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(9.2, 13.2);
    ctx.lineTo(14.2, 15.1);
    ctx.moveTo(22.8, 13.2);
    ctx.lineTo(17.8, 15.1);
    ctx.stroke();

    // Eyes
    circle(12.2, 16.8, 1.35, INK, null, 0);
    circle(19.8, 16.8, 1.35, INK, null, 0);

    // Snout
    ctx.beginPath();
    ctx.ellipse(16, 21.2, 4.2, 3.1, 0, 0, Math.PI * 2);
    ctx.fillStyle = SNOUT;
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 1.1 * (lineBoost || 1);
    ctx.stroke();

    // Nose
    ctx.beginPath();
    ctx.ellipse(16, 20.3, 1.5, 1.15, 0, 0, Math.PI * 2);
    ctx.fillStyle = INK;
    ctx.fill();

    // Frown
    ctx.beginPath();
    ctx.moveTo(13.4, 23.1);
    ctx.quadraticCurveTo(16, 21.6, 18.6, 23.1);
    ctx.strokeStyle = INK;
    ctx.lineWidth = mouthW;
    ctx.lineCap = "round";
    ctx.stroke();

    ctx.restore();
  }

  function startBearLattice(canvas, options) {
    if (!canvas) return null;

    var opts = Object.assign(
      {
        intensity: 1.1,
        speed: 1,
      },
      options || {}
    );

    var ctx = canvas.getContext("2d");
    var w = 0;
    var h = 0;
    var dpr = 1;
    var raf = 0;
    var t0 = performance.now();

    var intensity = opts.intensity;
    var intensityTarget = opts.intensity;
    var speed = opts.speed;

    var mx = 0;
    var my = 0;
    var pointerActive = false;

    // Spacing in CSS pixels between bear centers
    var spacing = 56;
    var baseScale = 1.05; // relative to 32px icon units

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
        mx = w * 0.5;
        my = h * 0.5;
      }
      // Slightly denser on small screens, airier on large
      spacing = Math.max(48, Math.min(68, Math.round(Math.min(w, h) / 14)));
    }

    function waveOffset(x, y, t) {
      var amp = 5.5 * intensity;
      var s = speed;
      var n1 = Math.sin(x * 0.018 + t * 1.6 * s) * amp;
      var n2 = Math.cos(y * 0.022 - t * 1.25 * s) * amp * 0.7;
      var n3 = Math.sin((x + y) * 0.012 + t * 2.1 * s) * amp * 0.45;

      // Cursor ripple (soft)
      var dx = x - mx;
      var dy = y - my;
      var dist = Math.sqrt(dx * dx + dy * dy);
      var ripple = 0;
      if (pointerActive || intensity > 1.2) {
        var reach = 180 + intensity * 40;
        if (dist < reach) {
          var fall = 1 - dist / reach;
          ripple =
            Math.sin(dist * 0.05 - t * 4.2 * s) *
            fall *
            fall *
            (7 + intensity * 2.5);
        }
      }
      return { dx: n1 + n3 * 0.35 + ripple * 0.35, dy: n2 + n3 + ripple };
    }

    function visibilityAt(sx, sy) {
      // Soft vignette — denser bears toward edges, quieter around password
      var nx = sx / Math.max(w, 1) - 0.5;
      var ny = sy / Math.max(h, 1) - 0.5;
      var r = Math.sqrt(nx * nx + ny * ny);
      // Center a bit calmer so Password field stays readable
      var centerCalm = 1 - Math.max(0, 1 - r * 2.2) * 0.45;
      var edge = Math.max(0.22, Math.min(1, 0.35 + r * 1.1));
      return edge * centerCalm;
    }

    function frame(now) {
      // Smooth intensity toward target (unlock ramp)
      intensity += (intensityTarget - intensity) * 0.08;

      var t = (now - t0) / 1000;
      ctx.clearRect(0, 0, w, h);

      // Solid navy already on body; optional deep tint
      ctx.fillStyle = "rgba(0, 0, 80, 0.15)";
      ctx.fillRect(0, 0, w, h);

      var cols = Math.ceil(w / spacing) + 3;
      var rows = Math.ceil(h / spacing) + 3;
      // Axis-aligned grid (no diagonal tilt); mild brick stagger for lattice feel
      var stagger = spacing * 0.5;

      var lineBoost = 1 + Math.max(0, intensity - 1) * 0.12;
      var scaleMul = baseScale * (0.92 + Math.min(intensity, 4) * 0.04);

      for (var row = -1; row < rows; row++) {
        for (var col = -1; col < cols; col++) {
          var sx = col * spacing + (row % 2 ? stagger : 0);
          var sy = row * spacing;

          var off = waveOffset(sx, sy, t);
          var x = sx + off.dx;
          var y = sy + off.dy;

          var vis = visibilityAt(x, y);
          // Subtle twinkle with the wave
          var pulse =
            0.82 +
            0.18 * Math.sin(t * 1.8 * speed + col * 0.7 + row * 0.55);
          var alpha = vis * pulse * Math.min(1, 0.55 + intensity * 0.12);
          // Scale breathes slightly with undulation
          var localScale =
            scaleMul *
            (0.88 + 0.12 * Math.sin(t * 2.2 * speed + col + row * 0.3));

          drawBear(ctx, x, y, localScale, alpha, lineBoost);
        }
      }

      raf = requestAnimationFrame(frame);
    }

    function onMove(e) {
      pointerActive = true;
      mx = e.clientX;
      my = e.clientY;
    }
    function onLeave() {
      pointerActive = false;
    }
    function onTouch(e) {
      if (!e.touches || !e.touches.length) return;
      pointerActive = true;
      mx = e.touches[0].clientX;
      my = e.touches[0].clientY;
    }

    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("mouseleave", onLeave);
    window.addEventListener("touchstart", onTouch, { passive: true });
    window.addEventListener("touchmove", onTouch, { passive: true });

    resize();
    raf = requestAnimationFrame(frame);

    return {
      setIntensity: function (v) {
        intensityTarget = Math.max(0.2, Number(v) || 1);
      },
      setSpeed: function (v) {
        speed = Math.max(0.2, Number(v) || 1);
      },
      destroy: function () {
        cancelAnimationFrame(raf);
        window.removeEventListener("resize", resize);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseleave", onLeave);
        window.removeEventListener("touchstart", onTouch);
        window.removeEventListener("touchmove", onTouch);
      },
    };
  }

  window.MotionBotBearLattice = {
    start: startBearLattice,
  };
})();
