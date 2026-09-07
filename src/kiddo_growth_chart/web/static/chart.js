/* Renderer: two projections of one dataset, plus discrete video mode.
 *
 * Nothing here interpolates a height. Video mode holds a value until the next
 * measurement and then springs to it, and the spring moves the figure only:
 * the peak of an overshoot is a height that never existed, so the ruler and
 * the readout snap. */
(() => {
  "use strict";
  const PALETTE = ["var(--k0)", "var(--k1)", "var(--k2)", "var(--k3)"];
  const CM_PER_IN = 2.54;
  const DAY_MS = 86400000;
  /* How far either side of a frame a portrait may come from. Wide enough that
   * most frames find one, and the date is printed under every portrait, so a
   * photo three months off says so rather than implying the frame's month. */
  const PHOTO_WINDOW_DAYS = 120;
  const MONTH = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const base = document.currentScript.src.replace(/\/static\/.*$/, "");
  const $ = (id) => document.getElementById(id);

  const state = {
    clock: "date", imperial: true, data: null,
    playing: false, frame: 0, timer: null, colors: new Map(),
  };

  const fmt = (cm) => {
    if (!state.imperial) return cm.toFixed(1) + " cm";
    // Round the inches before splitting, or 59.96in prints as 4'12.0".
    const tenths = Math.round((cm / CM_PER_IN) * 10);
    return `${Math.floor(tenths / 120)}′${((tenths % 120) / 10).toFixed(1)}″`;
  };
  const colorOf = (key) => state.colors.get(key) || "var(--fg)";

  async function fetchData(clock) {
    const res = await fetch(`${base}/data.json?clock=${clock}`, { credentials: "same-origin" });
    if (!res.ok) throw new Error(`data.json: ${res.status}`);
    return res.json();
  }

  /* ---- chart ------------------------------------------------------------ */
  const W = 960, H = 540, M = { t: 18, r: 96, b: 34, l: 52 };

  function drawChart() {
    const d = state.data, svg = $("chart");
    const xs = (v) => M.l + ((v - d.x.min) / Math.max(d.x.max - d.x.min, 1)) * (W - M.l - M.r);
    const ys = (cm) => H - M.b - ((cm - d.cm.min) / Math.max(d.cm.max - d.cm.min, 1e-6)) * (H - M.t - M.b);
    const el = (n, a, kids) => {
      const e = document.createElementNS("http://www.w3.org/2000/svg", n);
      for (const k in a) e.setAttribute(k, a[k]);
      (kids || []).forEach((c) => e.appendChild(c));
      return e;
    };
    svg.textContent = "";

    // horizontal gridlines, labelled in the active unit
    const stepCm = state.imperial ? 5 * CM_PER_IN : 10;
    const first = Math.ceil(d.cm.min / stepCm) * stepCm;
    for (let cm = first; cm <= d.cm.max; cm += stepCm) {
      svg.appendChild(el("line", { class: "grid", x1: M.l, x2: W - M.r, y1: ys(cm), y2: ys(cm) }));
      const t = el("text", { class: "axis-text", x: M.l - 8, y: ys(cm) + 4, "text-anchor": "end" });
      t.textContent = fmt(cm);
      svg.appendChild(t);
    }

    // x ticks: years on the calendar clock, whole ages on the age clock
    const ticks = xTicks(d);
    ticks.forEach(({ v, label }) => {
      svg.appendChild(el("line", { class: "grid", x1: xs(v), x2: xs(v), y1: H - M.b, y2: H - M.b + 5 }));
      const t = el("text", { class: "axis-text", x: xs(v), y: H - M.b + 18, "text-anchor": "middle" });
      t.textContent = label;
      svg.appendChild(t);
    });

    const labels = [];
    d.series.forEach((s) => {
      const stroke = colorOf(s.key);
      s.segments.forEach((sg) => {
        const a = s.points.find((p) => p.x === sg.a), b = s.points.find((p) => p.x === sg.b);
        if (!a || !b) return;
        svg.appendChild(el("line", {
          class: "seg" + (sg.mixed_method ? " mixed" : ""),
          x1: xs(a.x), y1: ys(a.cm), x2: xs(b.x), y2: ys(b.cm), stroke,
        }));
      });
      s.points.forEach((p) => {
        const c = el("circle", {
          class: "pt" + (p.method === "clinical" ? "" : " non-clinical"),
          cx: xs(p.x), cy: ys(p.cm), r: 4.5,
          fill: p.method === "clinical" ? stroke : "var(--panel)", stroke,
        });
        const title = el("title");
        title.textContent =
          `${s.name} — ${fmt(p.cm)} on ${p.date} (age ${p.age_years}y, ${p.method})`;
        c.appendChild(title);
        svg.appendChild(c);
      });
      const last = s.points[s.points.length - 1];
      if (last) labels.push({ name: s.name, x: xs(last.x) + 9, y: ys(last.cm) + 4, fill: stroke });
    });

    // On the age clock the lines converge, so end-labels land on top of each
    // other. Push them apart vertically before drawing.
    labels.sort((a, b) => a.y - b.y);
    const MIN_GAP = 15;
    for (let i = 1; i < labels.length; i++) {
      if (labels[i].y - labels[i - 1].y < MIN_GAP) labels[i].y = labels[i - 1].y + MIN_GAP;
    }
    labels.forEach((l) => {
      const t = el("text", { class: "series-label", x: l.x, y: l.y, fill: l.fill });
      t.textContent = l.name;
      svg.appendChild(t);
    });
  }

  function xTicks(d) {
    const out = [];
    if (d.clock === "age") {
      for (let y = 0; y * 365.2425 <= d.x.max; y++) {
        const v = y * 365.2425;
        if (v >= d.x.min - 365) out.push({ v, label: `${y}` });
      }
      return out.length > 14 ? out.filter((_, i) => i % 2 === 0) : out;
    }
    const y0 = new Date(d.x.min * 86400000).getUTCFullYear();
    const y1 = new Date(d.x.max * 86400000).getUTCFullYear();
    for (let y = y0; y <= y1; y++) {
      out.push({ v: Date.UTC(y, 0, 1) / 86400000, label: `${y}` });
    }
    return out.length > 14 ? out.filter((_, i) => i % 2 === 0) : out;
  }

  /* ---- video ------------------------------------------------------------ */
  /* Pixels per cm is fixed for the whole run, never per-frame. Normalising each
   * frame to the tallest kid makes a year where everyone grows look like a year
   * where nobody did. */
  const STAGE_PX = 300;
  const scale = () => STAGE_PX / Math.max(state.data.cm.max, 1);

  function buildRuler() {
    const ruler = $("ruler");
    ruler.textContent = "";
    const px = scale();
    const stepCm = state.imperial ? 30.48 : 25;   // a foot, or 25 cm
    for (let cm = stepCm; cm <= state.data.cm.max; cm += stepCm) {
      const line = document.createElement("div");
      line.className = "rule";
      line.style.bottom = `${cm * px + 26}px`;    // 26px: the name row below
      line.innerHTML = `<span>${fmt(cm)}</span>`;
      ruler.appendChild(line);
    }
  }

  function buildFigures() {
    const host = $("figures");
    host.textContent = "";
    state.data.series.forEach((s) => {
      const fig = document.createElement("div");
      fig.className = "figure";
      fig.dataset.key = s.key;
      fig.innerHTML =
        `<div class="portrait empty" data-role="portrait">·</div>` +
        `<div class="portrait-when" data-role="when"></div>` +
        `<div class="readout" data-role="readout"></div>` +
        `<div class="body" data-role="body" style="background:${colorOf(s.key)}"></div>` +
        `<div class="who">${s.name}</div>`;
      host.appendChild(fig);
    });
  }

  function showFrame(i) {
    const f = state.data.frames[i];
    if (!f) return;
    state.frame = i;
    $("scrub").value = i;
    $("frame-when").textContent =
      state.clock === "age" ? `age ${f.label}` : f.label;

    const px = scale();
    document.querySelectorAll(".figure").forEach((fig) => {
      const key = fig.dataset.key;
      const cm = f.heights[key];
      const body = fig.querySelector('[data-role="body"]');
      const readout = fig.querySelector('[data-role="readout"]');
      if (cm == null) { fig.style.visibility = "hidden"; return; }
      fig.style.visibility = "visible";
      // The readout snaps; only the drawn body may overshoot.
      readout.textContent = fmt(cm);
      const sprang = f.grew.includes(key);
      body.style.transition = "none";
      body.style.height = Math.round(cm * px) + "px";
      if (sprang && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        body.style.transform = "scaleY(.90)";
        requestAnimationFrame(() => {
          body.style.transition = "transform 620ms cubic-bezier(.18,1.6,.42,1)";
          body.style.transform = "scaleY(1)";
        });
      } else {
        body.style.transform = "scaleY(1)";
      }
      loadPortrait(fig, key, portraitDate(key, f));
    });
  }

  /* The calendar date a portrait should come from for this frame.
   *
   * On the calendar clock that is the frame's own moment, shared by everyone.
   * On the age clock it is each kid's OWN date at that age -- the view
   * superimposes four childhoods, so "age 8" must fetch each child at eight,
   * not all four in whichever year the frame happens to sit. */
  function portraitDate(key, frame) {
    const s = state.data.series.find((x) => x.key === key);
    if (!s) return null;
    const ms = state.clock === "age"
      ? Date.parse(`${s.dob}T00:00:00Z`) + frame.x * DAY_MS
      : frame.x * DAY_MS;
    const d = new Date(ms);
    return isNaN(d) ? null : d.toISOString().slice(0, 10);
  }

  /* A 404 means no photo of this kid in this window. Empty the slot rather
   * than leaving the previous portrait up: a face held over from an earlier
   * frame would read as this frame's, which is the one thing a matched-age
   * row must not do. */
  async function loadPortrait(fig, key, isoDate) {
    const slot = fig.querySelector('[data-role="portrait"]');
    const cap = fig.querySelector('[data-role="when"]');
    if (!isoDate) return clearPortrait(slot, cap);
    // One fetch per month, not per frame; several frames can land in the same
    // month and they would otherwise refetch the same photo.
    const stamp = isoDate.slice(0, 7);
    if (slot.dataset.when === stamp) return;
    slot.dataset.when = stamp;

    try {
      const url = `${base}/photo/${encodeURIComponent(key)}/${isoDate}`
                + `?window=${PHOTO_WINDOW_DAYS}`;
      const res = await fetch(url, { credentials: "same-origin" });
      if (slot.dataset.when !== stamp) return;   // a later frame overtook us
      if (!res.ok) return clearPortrait(slot, cap);
      const taken = res.headers.get("X-Photo-Taken") || "";
      const blob = await res.blob();
      if (slot.dataset.when !== stamp) return;
      showPortrait(slot, cap, blob, taken);
    } catch {
      clearPortrait(slot, cap);
    }
  }

  function showPortrait(slot, cap, blob, taken) {
    const img = new Image();
    img.alt = "";
    img.src = URL.createObjectURL(blob);
    img.onload = () => {
      if (slot.dataset.url) URL.revokeObjectURL(slot.dataset.url);
      slot.dataset.url = img.src;
      slot.className = "portrait";
      slot.textContent = "";
      slot.appendChild(img);
    };
    // The portrait's OWN date, not the frame's. The window is months wide, so
    // without this the picture silently claims to be from the moment shown.
    cap.textContent = taken
      ? `${MONTH[Number(taken.slice(5, 7)) - 1]} ${taken.slice(0, 4)}`
      : "";
  }

  function clearPortrait(slot, cap) {
    if (slot.dataset.url) { URL.revokeObjectURL(slot.dataset.url); delete slot.dataset.url; }
    slot.className = "portrait empty";
    slot.textContent = "·";
    cap.textContent = "";
  }

  function play(on) {
    state.playing = on;
    $("play").setAttribute("aria-pressed", String(on));
    $("play").textContent = on ? "❚❚ Pause" : "▶ Play years";
    $("chart-pane").hidden = on;
    $("video-pane").hidden = !on;
    clearInterval(state.timer);
    if (!on) return;
    buildFigures();
    buildRuler();
    $("scrub").max = String(state.data.frames.length - 1);
    showFrame(0);
    state.timer = setInterval(() => {
      const next = state.frame + 1;
      if (next >= state.data.frames.length) { play(false); return; }
      showFrame(next);
    }, 1100);
  }

  /* ---- wiring ----------------------------------------------------------- */
  function legend() {
    $("legend").innerHTML = state.data.series
      .map((s) => `<span class="chip"><span class="dot" style="background:${colorOf(s.key)}"></span>${s.name}` +
                  (s.mixed_methods ? ` <span class="muted">· mixed methods</span>` : "") + `</span>`)
      .join("");
  }

  async function setClock(clock) {
    state.clock = clock;
    state.data = await fetchData(clock);
    state.data.series.forEach((s, i) => {
      if (!state.colors.has(s.key)) state.colors.set(s.key, PALETTE[i % PALETTE.length]);
    });
    $("clock-date").classList.toggle("is-on", clock === "date");
    $("clock-age").classList.toggle("is-on", clock === "age");
    $("clock-date").setAttribute("aria-pressed", String(clock === "date"));
    $("clock-age").setAttribute("aria-pressed", String(clock === "age"));
    $("play").textContent = state.playing
      ? "❚❚ Pause" : (clock === "age" ? "▶ Play ages" : "▶ Play years");
    legend();
    drawChart();
    if (state.playing) play(true);
  }

  $("clock-date").onclick = () => setClock("date");
  $("clock-age").onclick = () => setClock("age");
  $("units").onclick = (e) => {
    state.imperial = !state.imperial;
    e.target.textContent = state.imperial ? "ft/in" : "cm";
    drawChart();
    if (state.playing) { buildRuler(); showFrame(state.frame); }
  };
  $("play").onclick = () => play(!state.playing);
  $("scrub").oninput = (e) => {
    if (!state.playing) return;
    clearInterval(state.timer);
    state.playing = true;
    showFrame(Number(e.target.value));
  };

  setClock("date").catch((err) => {
    document.querySelector(".wrap").insertAdjacentHTML(
      "beforeend", `<p class="error">Could not load data: ${err.message}</p>`);
  });
})();
