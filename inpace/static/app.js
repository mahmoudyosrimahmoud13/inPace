// Send a form the same way pressing its button would, so [data-nav-form] forms replace the page.
function sendForm(form) {
  if (form.requestSubmit) form.requestSubmit(); else form.submit();
}

// Go to a page after a change, and always load it fresh. Going to the page you're already on, with only a
// different #section (or none), makes the browser just scroll, so the change (a new colour, something you
// bought) wouldn't show until you reloaded by hand.
function goFresh(url) {
  const next = new URL(url, location.href);
  const samePage = next.origin === location.origin && next.pathname === location.pathname && next.search === location.search;
  if (samePage && next.hash) {
    history.replaceState(history.state, "", next.href);
    location.reload();
  } else {
    location.replace(next.href);
  }
}

// Small helpers only. The app works without JavaScript too.
document.querySelectorAll("[data-autosubmit]").forEach((input) => {
  input.addEventListener("change", () => {
    if (input.tagName === "SELECT") return;  // handled below
    if (input.type === "file" ? input.files.length : true) sendForm(input.form);
  });
  const zone = input.closest(".drop-zone");
  if (!zone) return;
  ["dragenter", "dragover"].forEach((e) => zone.addEventListener(e, () => zone.classList.add("over")));
  ["dragleave", "drop"].forEach((e) => zone.addEventListener(e, () => zone.classList.remove("over")));
});

document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const box = document.querySelector(btn.dataset.copy);
    try { await navigator.clipboard.writeText(box.value); }
    catch { box.select(); document.execCommand("copy"); }
    const old = btn.textContent;
    btn.textContent = document.documentElement.lang === "ar" ? "تم النسخ!" : "Copied!";
    setTimeout(() => (btn.textContent = old), 1800);
  });
});

// "More apps…" opens the system share menu where the window supports it (Signal, Messenger, Mail…).
if (navigator.share) {
  document.querySelectorAll("[data-share]").forEach((btn) => {
    btn.hidden = false;
    btn.addEventListener("click", () => {
      const text = document.querySelector(btn.dataset.share).value;
      navigator.share({ text }).catch(() => {});
    });
  });
}

document.querySelectorAll("[data-wordcount]").forEach((box) => {
  const need = +box.dataset.wordcount;
  const out = box.form.querySelector("[data-wordcount-out]");
  const update = () => {
    const n = box.value.trim() ? box.value.trim().split(/\s+/).length : 0;
    const of = box.dataset.of || '%s of at least %s words', ok = box.dataset.ok || '%s words ✓';
    out.textContent = n >= need ? ok.replace('%s', n) : of.replace('%s', n).replace('%s', need);
  };
  box.addEventListener("input", update);
  update();
});

document.querySelectorAll("[data-busy]").forEach((btn) => {
  btn.form.addEventListener("submit", () => { btn.disabled = true; btn.textContent = btn.dataset.busy; });
});

// A drawn diagram with zoom and full screen: − and + (or Ctrl + mouse wheel) zoom, drag to move around when
// it's bigger than the box, "Fit" shows all of it, and full screen fills the screen (Escape or the button closes it).
function diagramBox(svgText) {
  const ar = document.documentElement.lang === "ar";
  const T = ar ? { out: "تصغير", in: "تكبير", fit: "ملاءمة", full: "ملء الشاشة", close: "إغلاق ملء الشاشة" }
               : { out: "Zoom out", in: "Zoom in", fit: "Fit", full: "Full screen", close: "Close full screen" };
  const box = document.createElement("figure");
  box.className = "diagram-box";
  box.dir = "ltr";
  box.innerHTML = `<div class="diagram-tools" role="toolbar" aria-label="${T.in} / ${T.out}">
      <button type="button" data-z="out" title="${T.out}" aria-label="${T.out}">−</button>
      <span class="diagram-zoom" aria-live="polite">100%</span>
      <button type="button" data-z="in" title="${T.in}" aria-label="${T.in}">+</button>
      <button type="button" data-z="fit">${T.fit}</button>
      <button type="button" data-z="full" class="diagram-full-btn">⛶ <span>${T.full}</span></button>
    </div><div class="diagram-view" tabindex="0"><div class="diagram-canvas">${svgText}</div></div>`;
  const view = box.querySelector(".diagram-view"), svg = box.querySelector("svg"), label = box.querySelector(".diagram-zoom");
  const vb = svg.viewBox && svg.viewBox.baseVal;
  const natW = (vb && vb.width) || svg.getBoundingClientRect().width || 600, natH = (vb && vb.height) || 400;
  svg.removeAttribute("height");
  svg.style.maxWidth = "none";
  let z = 1, fitted = true;
  const fitZoom = () => {
    const full = box.classList.contains("is-full");
    const w = (view.clientWidth || natW) - 16, h = (view.clientHeight || natH) - 16;
    return full ? Math.min(w / natW, h / natH) : Math.min(1, w / natW);
  };
  const apply = (next, keepCenter = true) => {
    const cx = view.scrollLeft + view.clientWidth / 2, cy = view.scrollTop + view.clientHeight / 2, old = z;
    z = Math.max(0.2, Math.min(6, next));
    svg.style.width = Math.round(natW * z) + "px";
    svg.style.height = Math.round(natH * z) + "px";
    label.textContent = Math.round(z * 100) + "%";
    if (keepCenter) { view.scrollLeft = cx * z / old - view.clientWidth / 2; view.scrollTop = cy * z / old - view.clientHeight / 2; }
    box.classList.toggle("zoomed", natW * z > view.clientWidth + 2 || natH * z > view.clientHeight + 2);
  };
  const fit = () => { fitted = true; apply(fitZoom(), false); view.scrollLeft = view.scrollTop = 0; };
  const setFull = (on) => {
    box.classList.toggle("is-full", on);
    document.body.classList.toggle("diagram-open", on);
    const btn = box.querySelector(".diagram-full-btn");
    btn.querySelector("span").textContent = on ? T.close : T.full;
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    try {
      if (on && box.requestFullscreen && !document.fullscreenElement) box.requestFullscreen().catch(() => {});
      if (!on && document.fullscreenElement === box) document.exitFullscreen().catch(() => {});
    } catch (e) { /* the box still covers the window */ }
    requestAnimationFrame(fit);
    setTimeout(fit, 250);  // leaving the browser's full screen takes a moment: fit again once it's done
  };
  box.querySelector(".diagram-tools").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    fitted = false;
    if (b.dataset.z === "in") apply(z * 1.25);
    else if (b.dataset.z === "out") apply(z / 1.25);
    else if (b.dataset.z === "fit") fit();
    else if (b.dataset.z === "full") setFull(!box.classList.contains("is-full"));
  });
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && box.classList.contains("is-full")) setFull(false);
    else if (fitted) setTimeout(fit, 50);
  });
  box.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && box.classList.contains("is-full")) setFull(false);
    else if (e.key === "+" || e.key === "=") { fitted = false; apply(z * 1.25); }
    else if (e.key === "-") { fitted = false; apply(z / 1.25); }
    else if (e.key === "0") fit();
  });
  view.addEventListener("wheel", (e) => {
    if (!e.ctrlKey && !box.classList.contains("is-full")) return;  // plain scrolling still scrolls the lesson
    e.preventDefault();
    fitted = false;
    apply(z * (e.deltaY < 0 ? 1.12 : 1 / 1.12));
  }, { passive: false });
  let drag = null, pinch = null;  // one finger (or the mouse) drags a zoomed diagram; two fingers pinch to zoom
  const pts = new Map();
  const gap = () => { const [a, b] = [...pts.values()]; return Math.hypot(a.x - b.x, a.y - b.y) || 1; };
  view.addEventListener("pointerdown", (e) => {
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pts.size === 2 && (box.classList.contains("is-full") || box.classList.contains("zoomed"))) {
      pinch = { d: gap(), z };
      drag = null;
      return;
    }
    if (!box.classList.contains("zoomed") || e.button !== 0) return;
    drag = { x: e.clientX, y: e.clientY, l: view.scrollLeft, t: view.scrollTop };
    try { view.setPointerCapture(e.pointerId); } catch (err) {}
    view.classList.add("dragging");
  });
  view.addEventListener("pointermove", (e) => {
    if (pts.has(e.pointerId)) pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && pts.size === 2) { fitted = false; apply(pinch.z * gap() / pinch.d); return; }
    if (!drag) return;
    view.scrollLeft = drag.l - (e.clientX - drag.x);
    view.scrollTop = drag.t - (e.clientY - drag.y);
  });
  const stop = (e) => {
    pts.delete(e.pointerId);
    if (pts.size < 2) pinch = null;
    drag = null;
    view.classList.remove("dragging");
  };
  view.addEventListener("pointerup", stop);
  view.addEventListener("pointercancel", stop);
  window.addEventListener("resize", () => { if (fitted) fit(); });
  requestAnimationFrame(fit);
  return box;
}

// Diagrams: code blocks marked "mermaid" are drawn as pictures. The drawing code (static/mermaid) is big,
// so it only loads on pages that have a diagram. A diagram with a mistake shows its text and a note.
(() => {
  const blocks = [...document.querySelectorAll("pre.mermaid")];
  if (!blocks.length) return;
  const s = document.createElement("script");
  s.src = "/static/mermaid/mermaid.min.js?v=10.9.8";
  s.onload = async () => {
    const root = document.documentElement;
    const dark = root.dataset.theme === "dark" || (root.dataset.theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
    window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: dark ? "dark" : "default",
      fontFamily: getComputedStyle(document.body).fontFamily });
    for (const [i, pre] of blocks.entries()) {
      const text = pre.textContent;
      try {
        await window.mermaid.parse(text);
        const { svg } = await window.mermaid.render(`diagram-${i}`, text);
        pre.replaceWith(diagramBox(svg));
      } catch (e) {
        pre.classList.add("diagram-error");
        const note = document.createElement("span");
        note.className = "diagram-note";
        note.textContent = root.lang === "ar" ? "هذا الرسم فيه خطأ، فيظهر نصه بدلًا منه." : "This diagram has a mistake, so its text shows instead.";
        pre.appendChild(note);
      }
    }
  };
  document.head.appendChild(s);
})();

// Pictures in a lesson open in a viewer: fit to the screen, zoom with the buttons, the mouse wheel, + and −, or two
// fingers; drag to move around; double-click (or double-tap) to zoom in or fit again; ← and → for the other pictures
// of the lesson; Escape closes it. The page behind stays where it was.
(() => {
  const imgs = [...document.querySelectorAll(".prose img")].filter((img) => !img.closest("a, .diagram-box, .code-wrap"));
  if (!imgs.length) return;
  const ar = document.documentElement.lang === "ar";
  const T = ar ? { open: "تكبير الصورة", out: "تصغير", in: "تكبير", fit: "ملاءمة الشاشة", real: "الحجم الأصلي", rot: "تدوير",
                   prev: "الصورة السابقة", next: "الصورة التالية", close: "إغلاق", orig: "فتح الصورة وحدها", of: "من" }
               : { open: "Zoom into the picture", out: "Zoom out", in: "Zoom in", fit: "Fit to screen", real: "Actual size", rot: "Rotate",
                   prev: "Previous picture", next: "Next picture", close: "Close", orig: "Open the picture on its own", of: "of" };
  const P = { out: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5M8 11h6"/>', in: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5M8 11h6M11 8v6"/>',
              fit: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>', real: '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="M8 10v5M12 10v.01M12 14v.01M16 10v5"/>',
              rot: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>', prev: '<path d="M15 5l-7 7 7 7"/>', next: '<path d="M9 5l7 7-7 7"/>',
              close: '<path d="M6 6l12 12M18 6 6 18"/>', orig: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>' };
  const svg = (k) => `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[k]}</svg>`;
  const btn = (k) => `<button type="button" class="iv-btn" data-iv="${k}" title="${T[k]}" aria-label="${T[k]}">${svg(k)}</button>`;

  // A small button on each picture (and a click on the picture) opens the viewer.
  imgs.forEach((img, i) => {
    const holder = img.closest("figure") || img.parentElement;
    holder.classList.add("iv-holder");
    img.classList.add("iv-zoomable");
    img.addEventListener("click", () => open(i));
    const b = document.createElement("button");
    b.type = "button"; b.className = "iv-open"; b.title = T.open; b.setAttribute("aria-label", T.open); b.innerHTML = svg("fit");
    b.addEventListener("click", () => open(i));
    img.insertAdjacentElement("afterend", b);
  });

  let dlg, stage, pic, cap, label, counter, idx = 0, s = 1, fitS = 1, x = 0, y = 0, rot = 0, natW = 1, natH = 1, back = null;
  const MIN = 0.05, MAX = 8;
  function make() {
    dlg = document.createElement("div");
    dlg.className = "iv"; dlg.setAttribute("role", "dialog"); dlg.setAttribute("aria-modal", "true"); dlg.dir = "ltr";
    dlg.innerHTML = `<div class="iv-bar" role="toolbar">
        <span class="iv-count" aria-live="polite"></span>${btn("prev")}${btn("next")}
        <span class="iv-gap"></span>${btn("out")}<span class="iv-zoom" aria-live="polite">100%</span>${btn("in")}${btn("fit")}${btn("real")}${btn("rot")}
        <a class="iv-btn" data-iv="orig" target="_blank" rel="noopener" title="${T.orig}" aria-label="${T.orig}">${svg("orig")}</a>${btn("close")}
      </div><div class="iv-stage"><img class="iv-pic" alt="" draggable="false"></div><p class="iv-cap" dir="auto"></p>`;
    document.body.appendChild(dlg);
    stage = dlg.querySelector(".iv-stage"); pic = dlg.querySelector(".iv-pic"); cap = dlg.querySelector(".iv-cap");
    label = dlg.querySelector(".iv-zoom"); counter = dlg.querySelector(".iv-count");
    dlg.querySelector(".iv-bar").addEventListener("click", (e) => {
      const b = e.target.closest("[data-iv]");
      if (!b || b.dataset.iv === "orig") return;
      ({ prev: () => show(idx - 1), next: () => show(idx + 1), in: () => zoom(s * 1.25), out: () => zoom(s / 1.25),
         fit: fitNow, real: () => zoom(1), rot: () => { rot = (rot + 90) % 360; measure(); fitNow(); }, close })[b.dataset.iv]();
    });
    stage.addEventListener("wheel", (e) => {
      e.preventDefault();
      const f = Math.exp(-Math.max(-60, Math.min(60, e.deltaY)) * (e.ctrlKey ? 0.01 : 0.004));
      zoom(s * f, point(e));
    }, { passive: false });
    // One pointer drags, two pinch. A quick second click or tap zooms in where you tapped, or fits again.
    const pts = new Map();
    let drag = null, pinch = null, lastTap = 0;
    const gap = () => { const [a, b] = [...pts.values()]; return Math.hypot(a.x - b.x, a.y - b.y) || 1; };
    const mid = () => { const [a, b] = [...pts.values()]; const r = stage.getBoundingClientRect(); return { x: (a.x + b.x) / 2 - r.left, y: (a.y + b.y) / 2 - r.top }; };
    stage.addEventListener("pointerdown", (e) => {
      pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
      try { stage.setPointerCapture(e.pointerId); } catch (err) {}
      if (pts.size === 2) { pinch = { d: gap(), s, m: mid(), x, y }; drag = null; return; }
      const now = Date.now();
      if (now - lastTap < 320) { lastTap = 0; s > fitS * 1.05 ? fitNow() : zoom(Math.max(fitS * 2.5, 1), point(e)); return; }
      lastTap = now;
      drag = { px: e.clientX, py: e.clientY, x, y };
      stage.classList.add("dragging");
    });
    stage.addEventListener("pointermove", (e) => {
      if (!pts.has(e.pointerId)) return;
      pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pinch && pts.size === 2) {
        const m = mid(), ns = clamp(pinch.s * gap() / pinch.d);
        x = m.x - (pinch.m.x - pinch.x) * ns / pinch.s; y = m.y - (pinch.m.y - pinch.y) * ns / pinch.s; s = ns;
        place(); return;
      }
      if (drag) { x = drag.x + e.clientX - drag.px; y = drag.y + e.clientY - drag.py; place(); }
    });
    const up = (e) => { pts.delete(e.pointerId); if (pts.size < 2) pinch = null; if (!pts.size) { drag = null; stage.classList.remove("dragging"); } };
    stage.addEventListener("pointerup", up); stage.addEventListener("pointercancel", up);
    dlg.addEventListener("keydown", (e) => {
      const big = s > fitS * 1.02, step = 60;
      const k = e.key;
      if (k === "Escape") { e.preventDefault(); close(); }
      else if (k === "+" || k === "=") { e.preventDefault(); zoom(s * 1.25); }
      else if (k === "-" || k === "_") { e.preventDefault(); zoom(s / 1.25); }
      else if (k === "0") { e.preventDefault(); fitNow(); }
      else if (k === "1") { e.preventDefault(); zoom(1); }
      else if (k === "ArrowLeft" || k === "ArrowRight") {
        e.preventDefault();
        if (big) { x += k === "ArrowLeft" ? step : -step; place(); }
        else show(idx + ((k === "ArrowRight") !== ar ? 1 : -1));
      } else if ((k === "ArrowUp" || k === "ArrowDown") && big) { e.preventDefault(); y += k === "ArrowUp" ? step : -step; place(); }
      else if (k === "Tab") {  // keep the focus inside the viewer
        const f = [...dlg.querySelectorAll(".iv-btn:not([hidden]):not(:disabled)")];
        const i = f.indexOf(document.activeElement);
        e.preventDefault();
        f[(i + (e.shiftKey ? -1 : 1) + f.length) % f.length].focus();
      }
    });
    window.addEventListener("resize", () => { if (dlg.classList.contains("on")) fitNow(); });
  }
  const clamp = (v) => Math.max(MIN, Math.min(MAX, v));
  const point = (e) => { const r = stage.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  // The picture's size on screen, turned.
  const box = () => (rot % 180 ? { w: natH * s, h: natW * s } : { w: natW * s, h: natH * s });
  function place() {
    const W = stage.clientWidth, H = stage.clientHeight, b = box();
    // Smaller than the screen: keep it in the middle. Bigger: don't let it slide away from the edges.
    x = b.w <= W ? (W - b.w) / 2 : Math.min(0, Math.max(W - b.w, x));
    y = b.h <= H ? (H - b.h) / 2 : Math.min(0, Math.max(H - b.h, y));
    const cx = x + b.w / 2, cy = y + b.h / 2;
    pic.style.width = natW + "px"; pic.style.height = natH + "px";
    pic.style.transform = `translate(${cx - natW / 2}px, ${cy - natH / 2}px) rotate(${rot}deg) scale(${s})`;
    label.textContent = Math.round(s * 100) + "%";
    stage.classList.toggle("big", b.w > W + 1 || b.h > H + 1);
    dlg.querySelector('[data-iv="out"]').disabled = s <= MIN;
    dlg.querySelector('[data-iv="in"]').disabled = s >= MAX;
  }
  function zoom(next, at) {
    const W = stage.clientWidth, H = stage.clientHeight;
    at = at || { x: W / 2, y: H / 2 };
    const ns = clamp(next);
    x = at.x - (at.x - x) * ns / s; y = at.y - (at.y - y) * ns / s; s = ns;
    place();
  }
  function measure() {
    const W = stage.clientWidth, H = stage.clientHeight;
    const w = rot % 180 ? natH : natW, h = rot % 180 ? natW : natH;
    fitS = Math.min(1, (W - 24) / w, (H - 24) / h);
  }
  function fitNow() { measure(); s = fitS; x = y = 0; place(); }
  function show(i) {
    idx = (i + imgs.length) % imgs.length;
    const img = imgs[idx];
    rot = 0;
    const done = () => { natW = pic.naturalWidth || img.naturalWidth || 800; natH = pic.naturalHeight || img.naturalHeight || 600; fitNow(); };
    pic.onload = done;
    pic.src = img.currentSrc || img.src;
    pic.alt = img.alt || "";
    if (pic.complete && pic.naturalWidth) done();
    const fc = img.closest("figure") && img.closest("figure").querySelector("figcaption");
    cap.textContent = (fc && fc.textContent) || img.alt || "";
    cap.hidden = !cap.textContent;
    dlg.querySelector('[data-iv="orig"]').href = pic.src;
    const many = imgs.length > 1;
    counter.textContent = many ? `${idx + 1} ${T.of} ${imgs.length}` : "";
    dlg.querySelectorAll('[data-iv="prev"], [data-iv="next"]').forEach((b) => (b.hidden = !many));
  }
  function open(i) {
    if (!dlg) make();
    back = document.activeElement;
    dlg.classList.add("on");
    document.body.classList.add("iv-open-page");
    show(i);
    dlg.querySelector('[data-iv="close"]').focus();
  }
  function close() {
    dlg.classList.remove("on");
    document.body.classList.remove("iv-open-page");
    if (back && back.focus) back.focus({ preventScroll: true });
  }
})();

// Notes on a lesson. Select some of the lesson and a "Take a note" button appears next to it (under it on touch
// screens, where the phone's own menu sits above). It saves the sentence you selected and what you write, without
// leaving the page. Sentences you took notes on are highlighted, and "Show in the lesson" scrolls back to one.
(() => {
  const prose = document.querySelector(".prose[data-notes]");
  const list = document.getElementById("note-list");
  if (!prose || !list) return;
  const ar = document.documentElement.lang === "ar";
  const T = ar ? { take: "دوّن ملاحظة", save: "احفظ الملاحظة", cancel: "إلغاء", ph: "ملاحظتك (اختيارية)", fail: "تعذّر حفظ الملاحظة. هل inPace ما زال مفتوحًا؟", saved: "حُفظت الملاحظة" }
               : { take: "Take a note", save: "Save note", cancel: "Cancel", ph: "Your note (optional)", fail: "Couldn't save the note. Is inPace still open?", saved: "Note saved" };
  const pen = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/></svg>';
  const touch = matchMedia("(pointer: coarse)").matches;

  const fab = document.createElement("button");
  fab.type = "button"; fab.className = "note-fab"; fab.hidden = true; fab.innerHTML = `${pen}<span>${T.take}</span>`;
  const pop = document.createElement("div");
  pop.className = "note-pop"; pop.hidden = true; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", T.take);
  pop.innerHTML = `<blockquote dir="auto"></blockquote><textarea rows="3" dir="auto" placeholder="${T.ph}"></textarea>
    <p class="note-pop-err small" hidden></p>
    <div class="row wrap"><button type="button" class="btn primary" data-save>${T.save}</button><button type="button" class="btn ghost" data-cancel>${T.cancel}</button></div>`;
  document.body.append(fab, pop);
  const area = pop.querySelector("textarea"), err = pop.querySelector(".note-pop-err");
  let quote = "", where = null;

  const picked = () => {
    const sel = getSelection();
    if (!sel.rangeCount || sel.isCollapsed) return null;
    const r = sel.getRangeAt(0);
    if (!prose.contains(r.commonAncestorContainer)) return null;
    const text = sel.toString().replace(/\s+/g, " ").trim();
    return text.length >= 2 ? { r, text } : null;
  };
  // Next to the selection, inside the window: above it with a mouse, under it on touch screens.
  const place = (el, rect, below) => {
    const w = el.offsetWidth, h = el.offsetHeight;
    let top = below || rect.top < h + 16 ? rect.bottom + 10 : rect.top - h - 10;
    top = Math.min(top, innerHeight - h - 8);
    const left = Math.max(8, Math.min(innerWidth - w - 8, rect.left + rect.width / 2 - w / 2));
    el.style.top = top + scrollY + "px"; el.style.left = left + scrollX + "px";
  };
  let timer;
  const update = () => {
    if (!pop.hidden) return;
    const p = picked();
    if (!p) { fab.hidden = true; return; }
    quote = p.text.slice(0, 2000);
    where = p.r.getBoundingClientRect();
    fab.hidden = false;
    place(fab, where, touch);
  };
  document.addEventListener("selectionchange", () => { clearTimeout(timer); timer = setTimeout(update, touch ? 350 : 150); });
  fab.addEventListener("pointerdown", (e) => e.preventDefault());  // keep the selection while pressing
  const close = () => { pop.hidden = true; err.hidden = true; };
  fab.addEventListener("click", () => {
    fab.hidden = true;
    pop.querySelector("blockquote").textContent = quote;
    area.value = "";
    pop.hidden = false;
    place(pop, where, touch);
    area.focus({ preventScroll: true });
  });
  pop.querySelector("[data-cancel]").addEventListener("click", close);
  const save = async () => {
    const body = new FormData();
    body.append("quote", quote); body.append("text", area.value);
    const btn = pop.querySelector("[data-save]");
    btn.disabled = true;
    try {
      const res = await fetch(prose.dataset.notes, { method: "POST", body, headers: { "X-Inpace-Fetch": "1" } });
      if (!res.ok) throw new Error(await res.text());
      list.insertAdjacentHTML("beforeend", await res.text());
      const count = document.querySelector("[data-note-count]");
      if (count) { count.textContent = list.children.length; count.hidden = false; }
      close();
      getSelection().removeAllRanges();
      paint();
      const done = document.createElement("div");
      done.className = "note-saved"; done.setAttribute("role", "status"); done.textContent = T.saved;
      document.body.appendChild(done);
      setTimeout(() => done.remove(), 1800);
    } catch (e) {
      err.textContent = (e && e.message && e.message.length < 200 && !/fetch|network/i.test(e.message)) ? e.message : T.fail;
      err.hidden = false;
    } finally { btn.disabled = false; }
  };
  pop.querySelector("[data-save]").addEventListener("click", save);
  pop.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); save(); }
  });
  document.addEventListener("pointerdown", (e) => { if (!pop.hidden && !pop.contains(e.target)) close(); });

  // Find a saved sentence in the lesson again. Spaces and line breaks are ignored, because the text you select
  // across paragraphs and the text inside the page are spaced differently.
  const find = (q) => {
    const want = q.replace(/\s+/g, "");
    if (!want) return null;
    const walk = document.createTreeWalker(prose, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => n.parentElement.closest("button, .code-bar, .iv-open, .diagram-tools, script, style") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
    let flat = ""; const at = [];
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
      const t = n.nodeValue;
      for (let i = 0; i < t.length; i++) if (!/\s/.test(t[i])) { flat += t[i]; at.push([n, i]); }
    }
    const i = flat.indexOf(want);
    if (i < 0) return null;
    const r = document.createRange();
    r.setStart(at[i][0], at[i][1]);
    const end = at[i + want.length - 1];
    r.setEnd(end[0], end[1] + 1);
    return r;
  };
  const canPaint = window.CSS && CSS.highlights && typeof Highlight === "function";
  const paint = () => {
    if (!canPaint) return;
    const ranges = [...list.querySelectorAll("[data-quote]")].map((el) => find(el.dataset.quote)).filter(Boolean);
    CSS.highlights.set("inpace-notes", new Highlight(...ranges));
  };
  list.addEventListener("click", (e) => {
    const b = e.target.closest("[data-show-note]");
    if (!b) return;
    const r = find(b.closest("[data-quote]").dataset.quote);
    if (!r) return;
    const rect = r.getBoundingClientRect();
    scrollTo({ top: scrollY + rect.top - innerHeight / 3, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    if (canPaint) { CSS.highlights.set("inpace-note-now", new Highlight(r)); setTimeout(() => CSS.highlights.delete("inpace-note-now"), 2200); }
  });
  // Diagrams and pictures change the lesson after it loads, so paint again once they're in place.
  paint();
  setTimeout(paint, 1500);
})();

// Code blocks: language label + copy button.
document.querySelectorAll(".prose pre:not(.mermaid)").forEach((pre) => {
  const code = pre.querySelector("code");
  if (!code) return;
  const wrap = document.createElement("div");
  wrap.className = "code-wrap";
  pre.parentNode.insertBefore(wrap, pre);
  wrap.appendChild(pre);
  const lang = ((code.className.match(/language-([\w+-]+)/) || [])[1] || "code");
  const bar = document.createElement("div");
  bar.className = "code-bar";
  bar.innerHTML = `<span>${lang}</span><button type="button">Copy</button>`;
  wrap.appendChild(bar);
  const btn = bar.querySelector("button");
  const label = document.documentElement.lang === "ar" ? ["نسخ", "تم النسخ!"] : ["Copy", "Copied!"];
  btn.textContent = label[0];
  btn.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(code.innerText); } catch (e) {}
    btn.textContent = label[1];
    setTimeout(() => (btn.textContent = label[0]), 1500);
  });
});

// Celebration toast and a short burst of confetti.
function burstConfetti() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const c = document.createElement("canvas");
  c.className = "confetti";
  document.body.appendChild(c);
  const ctx = c.getContext("2d");
  c.width = innerWidth * devicePixelRatio; c.height = innerHeight * devicePixelRatio;
  const colors = ["#1F7A56", "#9FF0C8", "#F2B84B", "#7FB0F0", "#FF8FA3", "#3A506B"];
  const bits = Array.from({ length: 140 }, () => ({
    x: Math.random() * c.width, y: -Math.random() * c.height * 0.5, r: (4 + Math.random() * 5) * devicePixelRatio,
    vx: (Math.random() - 0.5) * 3, vy: 2 + Math.random() * 4, a: Math.random() * 6, va: (Math.random() - 0.5) * 0.3,
    color: colors[Math.floor(Math.random() * colors.length)],
  }));
  const start = performance.now();
  const frame = (t) => {
    ctx.clearRect(0, 0, c.width, c.height);
    for (const b of bits) {
      b.x += b.vx * devicePixelRatio; b.y += b.vy * devicePixelRatio; b.a += b.va; b.vy += 0.03;
      ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.a); ctx.fillStyle = b.color;
      ctx.fillRect(-b.r / 2, -b.r / 4, b.r, b.r / 2); ctx.restore();
    }
    if (t - start < 3200) requestAnimationFrame(frame); else c.remove();
  };
  requestAnimationFrame(frame);
}
document.querySelectorAll(".yay").forEach((yay, i) => {
  const close = () => { yay.classList.add("out"); setTimeout(() => yay.remove(), 300); };
  yay.querySelector(".yay-close").addEventListener("click", close);
  setTimeout(close, 7000 + i * 1500);
  if (i === 0 && yay.hasAttribute("data-confetti")) burstConfetti();
});

// Small notice used by the app window (e.g. "Saved to Downloads: file.json").
window.inpaceToast = (text) => {
  const t = document.createElement("div");
  t.className = "mini-toast";
  t.setAttribute("role", "status");
  t.textContent = document.documentElement.lang === "ar" ? text.replace("Saved to Downloads:", "حُفظ في التنزيلات:") : text;
  document.body.appendChild(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 300); }, 4000);
};

// Light / dark switch: changes right away, and inPace remembers it.
document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const root = document.documentElement;
    const now = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = now === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    const body = new FormData();
    body.append("theme", next);
    fetch("/theme", { method: "POST", body }).catch(() => {});
  });
});

// Online videos load only when you press play (nothing reaches the internet before that).
document.querySelectorAll(".embed-box").forEach((box) => {
  const btn = box.querySelector(".play");
  if (!btn) return;
  btn.addEventListener("click", () => {
    let el;
    if (box.dataset.embed) {
      el = document.createElement("iframe");
      el.src = box.dataset.ytKey ? youtubeSrc(box) : box.dataset.embed;
      el.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
      el.allowFullscreen = true;
      el.referrerPolicy = "strict-origin-when-cross-origin";
      el.title = btn.textContent.trim();
    } else {
      const tag = box.dataset.embedVideo ? "video" : "audio";
      el = document.createElement(tag);
      el.src = box.dataset.embedVideo || box.dataset.embedAudio;
      el.controls = true;
      el.autoplay = true;
    }
    const wrap = document.createElement("div");
    wrap.className = el.tagName === "IFRAME" ? "frame-wrap video-ratio" : "";
    wrap.appendChild(el);
    box.replaceWith(wrap);
    if (box.dataset.ytKey) youtubeRemember(el, box);
  });
  const restart = box.querySelector("[data-yt-restart]");
  if (restart) restart.addEventListener("click", () => { box.dataset.resume = "0"; restart.parentElement.hidden = true; btn.click(); });
});

// YouTube lessons: a lesson can be one piece of a long video (start and end), and it continues from the
// second you stopped at. The player tells us where it is through its own messages (no extra script).
function youtubeSrc(box) {
  const start = +box.dataset.start || 0, end = +box.dataset.end || 0, resume = +box.dataset.resume || 0;
  const from = resume > start + 5 && (!end || resume < end - 5) ? resume : start;
  let src = box.dataset.embed + "&origin=" + encodeURIComponent(location.origin);
  if (from) src += "&start=" + Math.floor(from);
  if (end) src += "&end=" + Math.floor(end);
  return src;
}
function youtubeRemember(frame, box) {
  const key = box.dataset.ytKey, end = +box.dataset.end || 0;
  let now = 0, length = 0, sent = -1;
  const send = (beacon) => {
    if (now <= 0 || Math.abs(now - sent) < 1) return;
    sent = now;
    const body = new FormData();
    body.append("key", key); body.append("t", now.toFixed(1)); body.append("d", String(end || length || 0));
    if (beacon && navigator.sendBeacon) navigator.sendBeacon("/media-pos", body);
    else fetch("/media-pos", { method: "POST", body, keepalive: true }).catch(() => {});
  };
  window.addEventListener("message", (ev) => {
    if (ev.source !== frame.contentWindow) return;
    let d = ev.data;
    try { if (typeof d === "string") d = JSON.parse(d); } catch (e) { return; }
    const info = d && d.info;
    if (!info || typeof info !== "object") return;
    if (typeof info.duration === "number" && info.duration > 0) length = info.duration;
    if (typeof info.currentTime === "number") {
      now = info.currentTime;
      if (Math.abs(now - sent) >= 5) send();
    }
    if (info.playerState === 2 || info.playerState === 0) send();  // paused or ended
  });
  const hello = () => {
    try { frame.contentWindow.postMessage(JSON.stringify({ event: "listening", id: key, channel: "widget" }), "*"); } catch (e) {}
  };
  frame.addEventListener("load", () => { hello(); setTimeout(hello, 1000); setTimeout(hello, 3000); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) send(true); });
  window.addEventListener("pagehide", () => send(true));
}

// Web pages in lessons can go full screen.
document.querySelectorAll("[data-fullscreen]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const frame = btn.closest("figure").querySelector("iframe");
    if (frame && frame.requestFullscreen) frame.requestFullscreen().catch(() => {});
  });
});

// "Choose folder": opens your computer's own folder window and fills in the path.
document.querySelectorAll("[data-pick-folder]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const input = document.querySelector(btn.dataset.pickFolder);
    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = "…";
    try {
      const r = await fetch("/pick-folder", { method: "POST" });
      const d = await r.json();
      if (d.folder && input) { input.value = d.folder; input.dispatchEvent(new Event("input")); }
      else if (input) input.focus();
    } catch (e) { if (input) input.focus(); }
    btn.disabled = false;
    btn.textContent = label;
  });
});

// Voice notes as proof for a task: record, stop, and it's saved like any other file.
document.querySelectorAll("[data-recorder]").forEach((box) => {
  const btn = box.querySelector(".rec-btn");
  const time = box.querySelector(".rec-time");
  const L = box.dataset;
  let rec = null, chunks = [], started = 0, timer = null;
  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  btn.addEventListener("click", async () => {
    if (rec && rec.state === "recording") { rec.stop(); return; }
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch (e) { time.textContent = L.lNomic; return; }
    const type = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg", "audio/mp4"].find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || "";
    rec = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
    chunks = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = async () => {
      clearInterval(timer);
      stream.getTracks().forEach((t) => t.stop());
      btn.disabled = true;
      btn.textContent = L.lSaving;
      const mime = rec.mimeType || type || "audio/webm";
      const ext = mime.includes("ogg") ? "ogg" : mime.includes("mp4") ? "m4a" : "webm";
      const stamp = new Date().toISOString().slice(0, 16).replace("T", " ").replace(":", "-");
      const body = new FormData();
      body.append("file", new Blob(chunks, { type: mime }), `voice note ${stamp}.${ext}`);
      const r = await fetch(box.dataset.upload, { method: "POST", body });
      goFresh(r.url || location.href);
    };
    rec.start(1000);
    started = Date.now();
    btn.classList.add("recording");
    btn.textContent = "■ " + L.lStop;
    timer = setInterval(() => (time.textContent = fmt(Math.round((Date.now() - started) / 1000))), 500);
  });
});

// ---------------------------------------------------------------------------
// Video player: big play button, ±10 s, speed, full screen, keyboard keys,
// and it continues from the second you stopped at (saved on this computer).
// ---------------------------------------------------------------------------
(() => {
  const fmt = (s) => {
    s = Math.max(0, Math.floor(s || 0));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = String(s % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${x}` : `${m}:${x}`;
  };
  const save = (key, t, d, speed, beacon) => {
    const body = new FormData();
    body.append("key", key); body.append("t", t.toFixed(1)); body.append("d", (d || 0).toFixed(1));
    if (speed) body.append("speed", speed);
    if (beacon && navigator.sendBeacon) navigator.sendBeacon("/media-pos", body);
    else fetch("/media-pos", { method: "POST", body, keepalive: true }).catch(() => {});
  };
  const remember = (media, key, getSpeed, getEnd) => {
    let last = 0;
    const end = () => (getEnd && getEnd()) || media.duration;
    const tick = (force, beacon) => {
      if (!media.duration) return;
      if (force || Math.abs(media.currentTime - last) >= 4) {
        last = media.currentTime;
        save(key, media.currentTime, end(), getSpeed && getSpeed(), beacon);
      }
    };
    media.addEventListener("timeupdate", () => tick(false));
    media.addEventListener("pause", () => tick(true));
    media.addEventListener("ended", () => save(key, end(), end()));
    addEventListener("pagehide", () => tick(true, true));
    return tick;
  };
  // lo and hi: a lesson can be one piece of a long video file. It starts at lo and stops at hi.
  const resumeAt = (media, start, lo = 0, hi = 0) => {
    const at = start > lo + 5 && (!hi || start < hi - 3) ? start : lo;
    if (at > 0) {
      const go = () => { if (media.duration && at < media.duration - 3) media.currentTime = at; };
      media.readyState >= 1 ? go() : media.addEventListener("loadedmetadata", go, { once: true });
    }
  };

  // Audio keeps the browser's own controls, but also continues where you stopped.
  document.querySelectorAll("audio[data-remember]").forEach((a) => {
    resumeAt(a, parseFloat(a.dataset.resume || "0"));
    remember(a, a.dataset.key);
  });

  const ICON = {
    play: '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M7 4.5v15l13-7.5z" fill="currentColor"/></svg>',
    pause: '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M6 4h4.5v16H6zM13.5 4H18v16h-4.5z" fill="currentColor"/></svg>',
    back: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><text x="12" y="15.5" font-size="7.5" text-anchor="middle" fill="currentColor" stroke="none" font-weight="800">10</text></svg>',
    fwd: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/><text x="12" y="15.5" font-size="7.5" text-anchor="middle" fill="currentColor" stroke="none" font-weight="800">10</text></svg>',
    vol: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/></svg>',
    mute: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/><path d="M17 9l5 6M22 9l-5 6"/></svg>',
    full: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="square"><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/></svg>',
    pip: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="5" width="18" height="14"/><rect x="12" y="12" width="7" height="5" fill="currentColor"/></svg>',
  };
  const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

  document.querySelectorAll("[data-player]").forEach((box) => {
    const v = box.querySelector("video");
    const L = box.dataset;
    const lo = parseFloat(L.start || "0") || 0, hiSet = parseFloat(L.end || "0") || 0;
    const hi = () => hiSet || v.duration || 0;
    const span = () => Math.max(0, hi() - lo);
    v.controls = false;
    let speed = parseFloat(L.speed || "1") || 1;
    v.playbackRate = speed;
    v.addEventListener("loadedmetadata", () => (v.playbackRate = speed));

    box.insertAdjacentHTML("beforeend", `
      <button type="button" class="pl-big" aria-label="${L.lPlay}">${ICON.play}</button>
      <div class="pl-toast" aria-live="polite"></div>
      <div class="pl-bar">
        <input type="range" class="pl-seek" min="0" max="1000" value="0" step="1" aria-label="${L.lPlay}">
        <div class="pl-row">
          <button type="button" class="pl-btn pl-play" title="${L.lPlay} (K)">${ICON.play}</button>
          <button type="button" class="pl-btn pl-back" title="${L.lBack} (J)">${ICON.back}</button>
          <button type="button" class="pl-btn pl-fwd" title="${L.lFwd} (L)">${ICON.fwd}</button>
          <button type="button" class="pl-btn pl-mute" title="${L.lMute} (M)">${ICON.vol}</button>
          <input type="range" class="pl-vol" min="0" max="1" step="0.05" value="1" aria-label="${L.lMute}">
          <span class="pl-time" dir="ltr">0:00 / 0:00</span>
          <span class="pl-grow"></span>
          <button type="button" class="pl-btn pl-speed" title="${L.lSpeed}">${speed}×</button>
          ${document.pictureInPictureEnabled ? `<button type="button" class="pl-btn pl-pip" title="${L.lPip}">${ICON.pip}</button>` : ""}
          <button type="button" class="pl-btn pl-full" title="${L.lFull} (F)">${ICON.full}</button>
        </div>
      </div>`);
    const $ = (c) => box.querySelector(c);
    const seek = $(".pl-seek"), time = $(".pl-time"), play = $(".pl-play"), big = $(".pl-big");
    const mute = $(".pl-mute"), vol = $(".pl-vol"), spd = $(".pl-speed"), toast = $(".pl-toast");
    let toastTimer, hideTimer, dragging = false;

    const say = (text) => {
      toast.textContent = text; toast.classList.add("on");
      clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove("on"), 1300);
    };
    const atEnd = () => hiSet && v.currentTime >= hiSet - 0.3;
    const toggle = () => {
      if (v.paused || v.ended) { if (atEnd()) v.currentTime = lo; v.play(); } else v.pause();
    };
    const jump = (s) => { v.currentTime = Math.min(Math.max(lo, v.currentTime + s), hi()); say((s > 0 ? "+" : "") + s + "s"); };
    const draw = () => {
      const d = span(), cur = Math.min(Math.max(0, v.currentTime - lo), d);
      if (!dragging) seek.value = d ? Math.round((cur / d) * 1000) : 0;
      seek.style.setProperty("--p", (seek.value / 10) + "%");
      const b = v.buffered.length && d ? Math.min(100, Math.max(0, v.buffered.end(v.buffered.length - 1) - lo) / d * 100) : 0;
      seek.style.setProperty("--b", b + "%");
      time.textContent = `${fmt(cur)} / ${fmt(d)}`;
    };
    const state = () => {
      const p = v.paused || v.ended;
      play.innerHTML = p ? ICON.play : ICON.pause;
      play.title = (p ? L.lPlay : L.lPause) + " (K)";
      box.classList.toggle("playing", !p);
      big.hidden = !p;
    };
    const wake = () => {
      box.classList.add("awake");
      clearTimeout(hideTimer);
      hideTimer = setTimeout(() => { if (!v.paused) box.classList.remove("awake"); }, 2500);
    };

    const tick = remember(v, L.key, () => speed, () => hiSet);
    resumeAt(v, parseFloat(L.resume || "0"), lo, hiSet);
    // The end of this lesson's piece works like the end of the video.
    const pieceDone = () => { v.pause(); v.currentTime = hiSet; state(); say(L.lEnded); tick(true);
      const done = document.querySelector(".lesson-actions, .lesson-foot"); done && done.scrollIntoView({ behavior: "smooth", block: "center" }); };
    if (hiSet) v.addEventListener("timeupdate", () => { if (!v.paused && v.currentTime >= hiSet) pieceDone(); });
    v.addEventListener("loadedmetadata", draw);
    v.addEventListener("timeupdate", draw);
    v.addEventListener("progress", draw);
    v.addEventListener("play", state); v.addEventListener("pause", state);
    v.addEventListener("ended", () => { state(); say(L.lEnded); const done = document.querySelector(".lesson-actions, .lesson-foot"); done && done.scrollIntoView({ behavior: "smooth", block: "center" }); });
    // Keep the keyboard keys working after a click (the big button disappears once it's pressed).
    box.addEventListener("click", (e) => { if (e.target.tagName !== "INPUT") box.focus({ preventScroll: true }); });
    v.addEventListener("click", toggle);
    v.addEventListener("dblclick", () => $(".pl-full").click());
    big.addEventListener("click", toggle);
    play.addEventListener("click", toggle);
    $(".pl-back").addEventListener("click", () => jump(-10));
    $(".pl-fwd").addEventListener("click", () => jump(10));
    seek.addEventListener("input", () => { dragging = true; seek.style.setProperty("--p", (seek.value / 10) + "%"); time.textContent = `${fmt((seek.value / 1000) * span())} / ${fmt(span())}`; });
    seek.addEventListener("change", () => { v.currentTime = lo + (seek.value / 1000) * span(); dragging = false; tick(true); });
    const volState = () => { mute.innerHTML = v.muted || v.volume === 0 ? ICON.mute : ICON.vol; vol.value = v.muted ? 0 : v.volume; };
    mute.addEventListener("click", () => { v.muted = !v.muted; volState(); });
    vol.addEventListener("input", () => { v.volume = parseFloat(vol.value); v.muted = v.volume === 0; volState(); });
    spd.addEventListener("click", () => {
      speed = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length] || 1;
      v.playbackRate = speed; spd.textContent = speed + "×"; say(speed + "×"); tick(true);
    });
    const pip = $(".pl-pip");
    pip && pip.addEventListener("click", () => (document.pictureInPictureElement ? document.exitPictureInPicture() : v.requestPictureInPicture()).catch(() => {}));
    $(".pl-full").addEventListener("click", () => {
      if (document.fullscreenElement) document.exitFullscreen();
      else (box.requestFullscreen ? box.requestFullscreen() : v.webkitEnterFullscreen && v.webkitEnterFullscreen());
    });
    box.addEventListener("mousemove", wake);
    box.addEventListener("keydown", (e) => {
      if (e.target.tagName === "INPUT" && e.target.type === "range" && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
      const k = e.key.toLowerCase();
      const act = { " ": toggle, k: toggle, j: () => jump(-10), l: () => jump(10), arrowleft: () => jump(-5), arrowright: () => jump(5),
        f: () => $(".pl-full").click(), m: () => mute.click(),
        arrowup: () => { v.volume = Math.min(1, v.volume + 0.1); v.muted = false; volState(); say(Math.round(v.volume * 100) + "%"); },
        arrowdown: () => { v.volume = Math.max(0, v.volume - 0.1); volState(); say(Math.round(v.volume * 100) + "%"); } }[k];
      if (act && !(e.target.tagName === "BUTTON" && (k === " " || k === "enter"))) { e.preventDefault(); act(); wake(); }
    });
    const restart = box.parentElement.querySelector("[data-restart]");
    restart && restart.addEventListener("click", () => { v.currentTime = lo; v.play(); restart.closest(".resume-hint").remove(); });
    state(); draw(); volState(); wake();
  });
})();

// AI course maker: show only the fields for the chosen starting point.
(() => {
  const radios = document.querySelectorAll('input[name="source"]');
  if (!radios.length) return;
  const show = () => {
    const v = (document.querySelector('input[name="source"]:checked') || {}).value || "topic";
    document.querySelectorAll("[data-for-source]").forEach((box) => {
      const on = box.dataset.forSource === v;
      box.hidden = !on;
      box.querySelectorAll("[data-required]").forEach((el) => (el.required = on));
    });
  };
  radios.forEach((r) => r.addEventListener("change", show));
  show();
})();

// "Make a course": show the fields for the chosen way to start.
(() => {
  const radios = document.querySelectorAll('input[name="start"]');
  if (!radios.length) return;
  const show = () => {
    const v = (document.querySelector('input[name="start"]:checked') || {}).value || "blank";
    document.querySelectorAll("[data-for-start]").forEach((box) => (box.hidden = box.dataset.forStart !== v));
  };
  radios.forEach((r) => r.addEventListener("change", show));
  show();
})();

// Lesson editor: formatting buttons and a live preview.
document.querySelectorAll("[data-lesson-editor]").forEach((form) => {
  const ta = form.querySelector("[data-md-target]");
  const edit = (fn) => {
    const s = ta.selectionStart, e = ta.selectionEnd, v = ta.value;
    const [text, a, b] = fn(v.slice(s, e), v, s, e);
    ta.setRangeText(text, s, e, "end");
    ta.focus();
    if (a !== undefined) ta.setSelectionRange(s + a, s + b);
    ta.dispatchEvent(new Event("input"));
  };
  form.querySelectorAll("[data-md]").forEach((b) => b.addEventListener("click", () => {
    const p = b.dataset.md;
    edit((sel, v, s) => {
      const atLineStart = s === 0 || v[s - 1] === "\n";
      const lines = (sel || "").split("\n").map((l) => p + l).join("\n") || p;
      return [(atLineStart ? "" : "\n") + lines];
    });
  }));
  form.querySelectorAll("[data-md-wrap]").forEach((b) => b.addEventListener("click", () => {
    const w = b.dataset.mdWrap;
    edit((sel) => [w + (sel || "text") + w, w.length, w.length + (sel || "text").length]);
  }));
  form.querySelectorAll("[data-md-block]").forEach((b) => b.addEventListener("click", () => {
    edit((sel) => ["\n```\n" + (sel || "code") + "\n```\n", 5, 5 + (sel || "code").length]);
  }));
  form.querySelectorAll("[data-md-link]").forEach((b) => b.addEventListener("click", () => {
    const url = prompt("Link (https://…)", "https://");
    if (url) edit((sel) => [`[${sel || url}](${url})`]);
  }));
  form.querySelectorAll("[data-md-video]").forEach((b) => b.addEventListener("click", () => {
    const ref = prompt("YouTube link, or a file path (video, audio, PDF, page, code)", "https://");
    if (ref) edit(() => [`\n![](${/\s/.test(ref) ? "<" + ref + ">" : ref})\n`]);
  }));
  // Write / Preview tabs
  const preview = form.querySelector(".preview-box");
  form.querySelectorAll("[data-tab]").forEach((tab) => tab.addEventListener("click", async () => {
    form.querySelectorAll("[data-tab]").forEach((t) => t.classList.toggle("on", t === tab));
    form.querySelectorAll("[data-pane]").forEach((p) => (p.hidden = p.dataset.pane !== tab.dataset.tab));
    if (tab.dataset.tab === "preview") {
      const body = new FormData();
      ["title", "content", "media"].forEach((k) => body.append(k, form.elements[k].value));
      preview.innerHTML = "…";
      const r = await fetch(form.dataset.preview, { method: "POST", body });
      preview.innerHTML = await r.text();
    }
  }));
});

// "Move to…" and other selects that save on change.
document.querySelectorAll("select[data-autosubmit]").forEach((s) => s.addEventListener("change", () => s.value && sendForm(s.form)));

// Tempo's welcome tour: a spotlight on each part of inPace, with Tempo explaining it.
(() => {
  const data = document.getElementById("tour-data");
  if (!data) return;
  const T = JSON.parse(data.textContent);
  const steps = T.steps;
  let i = 0;
  const shade = document.createElement("div");
  shade.className = "tour-shade";
  const spot = document.createElement("div");
  spot.className = "tour-spot";
  const card = document.createElement("div");
  card.className = "tour-card-pop";
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-modal", "true");
  card.setAttribute("aria-live", "polite");
  document.body.append(shade, spot, card);
  const visible = (el) => el && el.getClientRects().length > 0 && el.getBoundingClientRect().width > 0;
  // On a phone, People, Races, Settings and the rest live in the "More" sheet: open it (without its own backdrop,
  // so the tour stays on top) while a step points inside it, and close it again after.
  const sheet = document.querySelector("[data-more-sheet]");
  const tabbar = document.querySelector(".tabbar");
  const sheetOpen = (on) => {
    if (!sheet) return;
    if (on && !sheet.open) { sheet.setAttribute("open", ""); sheet.classList.add("tour-open"); }
    if (!on && sheet.classList.contains("tour-open")) { sheet.removeAttribute("open"); sheet.classList.remove("tour-open"); }
  };
  const finish = () => {
    fetch("/tour/done", { method: "POST" }).catch(() => {});
    sheetOpen(false);
    [shade, spot, card].forEach((x) => x.remove());
    document.removeEventListener("keydown", keys);
    if (location.search.includes("tour=1")) history.replaceState(null, "", location.pathname);
  };
  const place = () => {
    const s = steps[i];
    // A target can list a few places ("the sidebar link, or the phone tab"): use the first one on screen.
    const found = s.target ? s.target.split(",").map((t) => document.querySelector(t.trim())).filter(Boolean) : [];
    let el = found.find((x) => visible(x) && !(sheet && sheet.contains(x)));
    const inSheet = !el && sheet && visible(tabbar) && found.find((x) => sheet.contains(x));
    sheetOpen(Boolean(inSheet));
    if (inSheet) el = inSheet;
    card.classList.remove("center");
    if (visible(el)) {
      el.scrollIntoView({ block: "nearest" });
      const r = el.getBoundingClientRect(), pad = 6;
      Object.assign(spot.style, { display: "block", top: r.top - pad + "px", left: r.left - pad + "px",
        width: r.width + pad * 2 + "px", height: r.height + pad * 2 + "px" });
      shade.classList.add("clear");
      const narrow = innerWidth < 700;
      const cw = narrow ? innerWidth - 32 : Math.min(380, innerWidth - 32);
      card.style.width = cw + "px";
      const ch = card.offsetHeight;
      let left, top;
      if (narrow) {
        // A phone: the card goes across the screen, above the spot when the spot is low (the tab bar, the More
        // sheet), below it when it's high, so it never covers what it talks about.
        left = 16;
        top = r.top > innerHeight / 2 ? r.top - pad - ch - 14 : r.bottom + pad + 14;
        top = Math.max(12, Math.min(top, innerHeight - ch - 12));
      } else {
        left = r.right + 18; top = Math.max(16, Math.min(r.top - 20, innerHeight - ch - 16));
        if (left + cw > innerWidth - 16) left = r.left - cw - 18;              // no room on the right
        if (left < 16) { left = Math.max(16, Math.min(r.left, innerWidth - cw - 16)); top = r.bottom + 14; } // below
        if (top + ch > innerHeight - 16) top = Math.max(16, r.top - ch - 14);   // above
      }
      Object.assign(card.style, { left: left + "px", top: top + "px" });
    } else {
      spot.style.display = "none";
      shade.classList.remove("clear");
      card.classList.add("center");
      Object.assign(card.style, { left: "", top: "", width: "" });
    }
  };
  const draw = () => {
    const s = steps[i], last = i === steps.length - 1;
    const tempo = document.getElementById("tour-tempo-" + s.mood) || document.getElementById("tour-tempo-happy");
    card.innerHTML = `
      <div class="tour-tempo">${tempo ? tempo.innerHTML : ""}</div>
      <div class="tour-body">
        <p class="tour-count">${i + 1} / ${steps.length}</p>
        <h3></h3><p class="tour-text"></p>
        <div class="tour-actions">
          ${i > 0 ? `<button type="button" class="btn" data-t="back">${T.back}</button>` : `<button type="button" class="btn ghost" data-t="skip">${T.skip}</button>`}
          <button type="button" class="btn primary" data-t="next">${last ? T.done : T.next}</button>
        </div>
      </div>`;
    card.querySelector("h3").textContent = s.title;
    card.querySelector(".tour-text").textContent = s.text;
    card.querySelector('[data-t="next"]').addEventListener("click", () => (last ? finish() : go(1)));
    const b = card.querySelector('[data-t="back"]'); b && b.addEventListener("click", () => go(-1));
    const k = card.querySelector('[data-t="skip"]'); k && k.addEventListener("click", finish);
    place();
    card.querySelector('[data-t="next"]').focus({ preventScroll: true });
  };
  const go = (d) => { i = Math.max(0, Math.min(steps.length - 1, i + d)); draw(); };
  const keys = (e) => {
    if (e.key === "Escape") finish();
    else if (e.key === "ArrowRight" && document.dir !== "rtl" || e.key === "ArrowLeft" && document.dir === "rtl") go(1);
    else if (e.key === "ArrowLeft" && document.dir !== "rtl" || e.key === "ArrowRight" && document.dir === "rtl") go(-1);
  };
  document.addEventListener("keydown", keys);
  addEventListener("resize", place);
  shade.addEventListener("click", () => {});
  draw();
})();

// Search and jump (Ctrl+K or /): courses, lessons, tasks, people and pages.
(() => {
  const btn = document.querySelector("[data-search]");
  const L = document.getElementById("search-labels");
  if (!btn || !L) return;
  let items = null, box = null, list, input, sel = 0, shown = [];
  const norm = (s) => (s || "").toLowerCase().normalize("NFKD").replace(/[ً-ٰٟ]/g, "");
  const score = (it, q) => {
    const t = norm(it.t), k = norm(it.k);
    if (!q) return 1;
    let s = 0;
    for (const w of q.split(/\s+/).filter(Boolean)) {
      if (t.startsWith(w)) s += 5; else if (t.includes(w)) s += 3; else if (k.includes(w)) s += 1; else return 0;
    }
    return s;
  };
  const render = () => {
    const q = norm(input.value.trim());
    shown = items.map((it) => [score(it, q), it]).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0]).slice(0, 40).map(([, it]) => it);
    sel = Math.min(sel, Math.max(0, shown.length - 1));
    list.innerHTML = "";
    if (!shown.length) { const li = document.createElement("li"); li.className = "empty"; li.textContent = L.dataset.empty; list.append(li); return; }
    shown.forEach((it, i) => {
      const li = document.createElement("li");
      li.className = i === sel ? "on" : "";
      li.setAttribute("role", "option");
      li.innerHTML = "<b dir='auto'></b><span dir='auto'></span>";
      li.firstChild.textContent = it.t; li.lastChild.textContent = it.k;
      li.addEventListener("click", () => (location.href = it.u));
      li.addEventListener("mousemove", () => { if (sel !== i) { sel = i; mark(); } });
      list.append(li);
    });
  };
  const mark = () => [...list.children].forEach((li, i) => { li.classList.toggle("on", i === sel); if (i === sel) li.scrollIntoView({ block: "nearest" }); });
  const close = () => { box && box.remove(); box = null; };
  const open = async () => {
    if (box) return;
    box = document.createElement("div");
    box.className = "search-pop";
    box.innerHTML = `<div class="search-card" role="dialog" aria-modal="true"><input type="search" autocomplete="off"><ul role="listbox"></ul><p class="small muted"></p></div>`;
    document.body.append(box);
    input = box.querySelector("input"); list = box.querySelector("ul");
    input.placeholder = L.dataset.placeholder; box.querySelector("p").textContent = L.dataset.hint;
    box.addEventListener("click", (e) => e.target === box && close());
    input.addEventListener("input", () => { sel = 0; render(); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(shown.length - 1, sel + 1); mark(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(0, sel - 1); mark(); }
      else if (e.key === "Enter" && shown[sel]) location.href = shown[sel].u;
      else if (e.key === "Escape") close();
    });
    input.focus();
    if (!items) { try { items = await (await fetch("/nav.json")).json(); } catch (e) { items = []; } }
    render();
  };
  btn.addEventListener("click", open);
  document.addEventListener("keydown", (e) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(e.target.tagName) || e.target.isContentEditable;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); }
    else if (e.key === "/" && !typing && !e.target.closest("[data-player]")) { e.preventDefault(); open(); }
    else if (!typing && !e.altKey && !e.ctrlKey && !e.metaKey && (e.key === "n" || e.key === "p") &&
             !e.target.closest("[data-player]")) {
      // N and P: next and previous lesson.
      const a = document.querySelector(e.key === "n" ? "[data-key-next]" : "[data-key-prev]");
      if (a) { e.preventDefault(); a.hasAttribute("data-replace") ? location.replace(a.href) : (location.href = a.href); }
    }
  });
})();

// Back and forward: the app window has no browser buttons, so inPace has its own (top left),
// plus Alt+← / Alt+→ and the side buttons on a mouse.
(() => {
  const back = document.querySelector("[data-nav-back]"), fwd = document.querySelector("[data-nav-fwd]");
  if (!back) return;
  // Back works like in a phone app (see inpaceBack below): it closes what's open, leaves a main page for Home,
  // and otherwise goes one page back.
  const goBack = () => (window.inpaceBack ? window.inpaceBack() : history.back());
  const goFwd = () => history.forward();
  back.addEventListener("click", goBack);
  fwd.addEventListener("click", goFwd);
  // Show which way you can go, where the window can tell.
  const nav = window.navigation;
  const sync = () => {
    if (!nav || nav.canGoBack === undefined) return;
    back.disabled = location.pathname === "/";
    fwd.disabled = !nav.canGoForward;
  };
  back.disabled = location.pathname === "/";
  sync();
  if (nav) nav.addEventListener("currententrychange", sync);
  document.addEventListener("keydown", (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) || e.target.isContentEditable) return;
    // Left is always back, like in a browser, also in Arabic.
    if (e.key === "ArrowLeft") { e.preventDefault(); goBack(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); goFwd(); }
  });
  window.addEventListener("mouseup", (e) => {
    if (e.button === 3) { e.preventDefault(); goBack(); }
    else if (e.button === 4) { e.preventDefault(); goFwd(); }
  });
})();

// My courses: type to find a course by its title, description, modules or lessons.
(() => {
  const box = document.querySelector("[data-course-filter]");
  if (!box) return;
  const cards = [...document.querySelectorAll("[data-course-search]")];
  const none = document.querySelector("[data-course-none]");
  let topic = "";  // the library's topic buttons narrow the list too
  const run = () => {
    const words = box.value.toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    cards.forEach((c) => {
      const ok = words.every((w) => c.dataset.courseSearch.includes(w)) &&
        (!topic || (c.dataset.tags || "").split("|").includes(topic));
      c.hidden = !ok;
      shown += ok;
    });
    if (none) none.hidden = shown > 0;
    document.querySelectorAll("[data-folder-box]").forEach((f) => {
      f.hidden = words.length > 0 && !f.querySelector("[data-course-search]:not([hidden])");
      if (words.length && !f.hidden) f.querySelector("details").open = true;
    });
  };
  box.addEventListener("input", run);
  document.querySelectorAll("[data-lib-topic]").forEach((b) => b.addEventListener("click", () => {
    topic = b.dataset.libTopic;
    document.querySelectorAll("[data-lib-topic]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    run();
  }));
  if (box.value) run();  // opened from a shared link: show that course
})();

// A library course's sample lesson: shown folded, with a button to read all of it.
(() => {
  const box = document.querySelector("[data-lib-fade]");
  const more = document.querySelector("[data-lib-more]");
  if (!box || !more) return;
  const open = () => { box.classList.add("open"); more.parentElement.hidden = true; };
  if (box.scrollHeight <= box.clientHeight + 10) open();
  more.addEventListener("click", open);
})();

// ---- Android app ---------------------------------------------------------------------------------
// In the Android app there is no browser, so downloads, folder picking and sharing go through the app
// (window.InPaceAndroid, provided by the Flutter shell).
(() => {
  const bridge = window.InPaceAndroid;
  if (!bridge) return;
  document.documentElement.classList.add("android");
  const send = (msg) => bridge.postMessage(JSON.stringify(msg));
  const DOWNLOADS = /^\/(courses\/[^/]+\/(export|publish\/file)|milestones\/[^/]+\/(export|files|record)|people\/card|outbox\/|files\/[0-9a-f]{64}$|races\/[^/]+\/(invite|update)$|me\/turtle\.svg$|island\/share\.svg$)/;

  // Downloads: the app saves or shares the file.
  document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a[href]");
    if (!a) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return;
    if (a.hasAttribute("download") || DOWNLOADS.test(url.pathname)) {
      e.preventDefault();
      send({ type: "download", url: url.href });
    }
  }, true);

  // Forms that answer with a file (backups): fetch it here and hand the file to the app.
  document.addEventListener("submit", async (e) => {
    const form = e.target;
    const picture = form.matches('form[action="/me/turtle.png"], form[action="/island/share.png"]');
    if (!form.matches('form[action="/settings/backup"]') && !picture) return;
    if (picture && !form.png.value) return;  // the picture isn't drawn yet
    e.preventDefault();
    const r = await fetch(form.action, { method: "POST", body: new FormData(form) });
    if (!r.ok || !(r.headers.get("content-disposition") || "").includes("attachment")) { location.href = r.url; return; }
    const cd = r.headers.get("content-disposition") || "";
    const m = cd.match(/filename\*=UTF-8''([^;]+)/);
    const name = m ? decodeURIComponent(m[1]) : "inPace file";
    const buf = new Uint8Array(await r.arrayBuffer());
    let bin = "";
    for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    send({ type: "file", name, data: btoa(bin) });
  }, true);

  // "Choose folder" uses Android's folder picker.
  window.inpaceFolderPicked = (selector, path) => {
    const input = document.querySelector(selector);
    if (input && path) { input.value = path; input.dispatchEvent(new Event("input")); }
  };
  document.querySelectorAll("[data-pick-folder]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopImmediatePropagation();
      send({ type: "pickFolder", target: btn.dataset.pickFolder });
    }, true);
  });

  // Reminders: the app schedules Android notifications from inPace's plan (reminders, alarms and Tempo's
  // nudges). The plan is sent again whenever you use inPace (at most every 30 minutes), so it stays up to date.
  const onReminders = location.pathname === "/reminders";
  const syncPlan = async (force) => {
    let last = 0;
    try { last = +localStorage.getItem("inpace-plan-at") || 0; } catch (e) {}
    if (!force && Date.now() - last < 30 * 60e3) return;
    try {
      const r = await fetch("/reminders/plan.json");
      if (!r.ok) return;
      send({ type: "notifySync", plan: await r.json() });
      try { localStorage.setItem("inpace-plan-at", String(Date.now())); } catch (e) {}
    } catch (e) {}
  };
  syncPlan(onReminders);
  window.inpaceNotifyState = (state) => {
    const ask = document.querySelector("[data-notify-ask]");
    if (ask) ask.hidden = !!(state && state.enabled);
    if (state && state.enabled) syncPlan(true);
  };
  if (onReminders) send({ type: "notifyState" });
  document.querySelectorAll("[data-notify-allow]").forEach((btn) =>
    btn.addEventListener("click", () => send({ type: "notifyAllow" })));
  document.querySelectorAll("[data-notify-test]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      try {
        const plan = await (await fetch("/reminders/plan.json")).json();
        send({ type: "notifyTest", kind: btn.dataset.notifyTest, message: plan.test, labels: plan.labels });
      } catch (err) {}
    });
  });

  // Focus trip: the app shows Tempo's countdown in a notification while a trip runs, and it keeps counting
  // when inPace is in the background or closed. Every page tells the app how the trip stands now.
  let trip = null;
  try { trip = JSON.parse((document.getElementById("inpace-trip") || {}).textContent || "null"); } catch (e) {}
  if (document.getElementById("inpace-trip")) send({ type: "trip", trip });
  window.inpaceTripChanged = async () => {
    try {
      const r = await fetch("/island/live.json", { cache: "no-store" });
      if (r.ok) { trip = (await r.json()).trip; send({ type: "trip", trip }); }
    } catch (e) {}
  };
  window.inpaceTripPaused = () => { if (trip) send({ type: "trip", trip: { ...trip, state: "paused", ends_ms: null } }); };

  // "More apps…" opens Android's share sheet.
  document.querySelectorAll("[data-share]").forEach((btn) => {
    btn.hidden = false;
    btn.addEventListener("click", () => send({ type: "share", text: document.querySelector(btn.dataset.share).value }));
  });
})();

// ---- Add a course: sort the files ------------------------------------------------------------------
// Sections and files live in the page; on submit they're written into one hidden "plan" field.
(() => {
  const form = document.querySelector("[data-organizer]");
  if (!form) return;
  const box = form.querySelector("[data-sections]");
  const out = form.querySelector("[data-out]");
  const outLabel = form.querySelector("[data-out-label]").innerHTML.trim();
  const sections = () => [...box.querySelectorAll(":scope > [data-sec]")];
  const lists = () => [...sections().map((s) => s.querySelector("[data-files]")), out.querySelector("[data-files]")];
  const size = (n) => {
    const u = ["bytes", "KB", "MB", "GB", "TB"];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return i ? n.toFixed(1) + " " + u[i] : n + " bytes";
  };

  const refresh = () => {
    const secs = sections();
    secs.forEach((s, i) => {
      s.querySelector(".org-num").textContent = i + 1;
      s.querySelector("[data-sec-up]").disabled = i === 0;
      s.querySelector("[data-sec-down]").disabled = i === secs.length - 1;
      s.classList.toggle("empty", !s.querySelector(".org-file"));
    });
    const names = secs.map((s, i) => `${i + 1}. ${s.querySelector("[data-sec-title]").value || "…"}`);
    lists().forEach((list, li) => {
      const rows = [...list.children];
      rows.forEach((row, ri) => {
        const sel = row.querySelector("[data-move]");
        sel.innerHTML = "";
        names.forEach((n, i) => sel.add(new Option(n, i, false, i === li)));
        sel.add(new Option("— " + outLabel, "out", false, li === names.length));
        row.querySelector("[data-file-up]").disabled = ri === 0;
        row.querySelector("[data-file-down]").disabled = ri === rows.length - 1;
      });
    });
    let total = 0, n = 0;
    secs.forEach((s) => s.querySelectorAll(".org-file").forEach((r) => { total += +r.dataset.size; n++; }));
    const count = form.querySelector("[data-count]");
    if (count) count.textContent = count.dataset.msg.replace("{n}", n).replace("{s}", secs.filter((s) => s.querySelector(".org-file")).length);
    const space = form.querySelector("[data-space]");
    if (space) {
      const free = +space.dataset.free;
      const full = free && total > free;
      const msg = full ? space.dataset.full : total > 2 * 1024 ** 3 ? space.dataset.big : space.dataset.msg;
      space.textContent = msg.replace("{size}", size(total)).replace("{free}", size(free));
      space.classList.toggle("warn", total > 2 * 1024 ** 3 || full);
      const copy = form.querySelector("[data-copy-choice]");
      copy.disabled = !!full;
      if (full && copy.checked) form.querySelector('[name=storage][value=keep]').checked = true;
    }
  };

  const moveTo = (row, target) => {
    const list = target === "out" ? out.querySelector("[data-files]") : sections()[+target].querySelector("[data-files]");
    list.appendChild(row);
    refresh();
    row.querySelector("[data-move]").focus();
  };

  form.addEventListener("change", (e) => {
    if (e.target.matches("[data-move]")) moveTo(e.target.closest(".org-file"), e.target.value);
  });
  form.addEventListener("input", (e) => { if (e.target.matches("[data-sec-title]")) refresh(); });
  form.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const row = b.closest(".org-file");
    const sec = b.closest("[data-sec]");
    if (b.matches("[data-file-up]") && row.previousElementSibling) row.parentNode.insertBefore(row, row.previousElementSibling);
    else if (b.matches("[data-file-down]") && row.nextElementSibling) row.parentNode.insertBefore(row.nextElementSibling, row);
    else if (b.matches("[data-sec-up]") && sec.previousElementSibling) box.insertBefore(sec, sec.previousElementSibling);
    else if (b.matches("[data-sec-down]") && sec.nextElementSibling) box.insertBefore(sec.nextElementSibling, sec);
    else if (b.matches("[data-sec-remove]")) {
      sec.querySelectorAll(".org-file").forEach((r) => out.querySelector("[data-files]").appendChild(r));
      sec.remove();
    } else if (b.matches("[data-sec-add]")) {
      const s = form.querySelector("[data-sec-tpl]").content.firstElementChild.cloneNode(true);
      box.appendChild(s);
      refresh();
      const t = s.querySelector("[data-sec-title]");
      t.focus(); t.select();
      return;
    } else return;
    refresh();
    b.focus();
  });

  // Drag and drop with a mouse (on phones, "Move to" and the arrows do the same).
  let dragged = null;
  form.addEventListener("dragstart", (e) => {
    dragged = e.target.closest && e.target.closest(".org-file");
    if (!dragged) return;
    dragged.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", dragged.dataset.file);
  });
  form.addEventListener("dragend", () => { if (dragged) dragged.classList.remove("dragging"); dragged = null; refresh(); });
  form.addEventListener("dragover", (e) => {
    if (!dragged) return;
    const sec = e.target.closest("[data-sec], [data-out]");
    if (!sec) return;
    e.preventDefault();
    const list = sec.querySelector("[data-files]");
    const over = e.target.closest(".org-file");
    if (over && over !== dragged) {
      const r = over.getBoundingClientRect();
      list.insertBefore(dragged, e.clientY > r.top + r.height / 2 ? over.nextSibling : over);
    } else if (!over) list.appendChild(dragged);
  });
  form.addEventListener("drop", (e) => { if (dragged) e.preventDefault(); });

  form.addEventListener("submit", () => {
    const names = {};
    const plan = { title: form.querySelector("[data-title]").value, names, sections: sections().map((s) => ({
      title: s.querySelector("[data-sec-title]").value,
      files: [...s.querySelectorAll(".org-file")].map((r) => {
        const inp = r.querySelector(".org-name");
        if (inp.value.trim() && inp.value !== inp.dataset.default) names[r.dataset.file] = inp.value.trim();
        return r.dataset.file;
      }),
    })) };
    form.querySelector("[data-plan]").value = JSON.stringify(plan);
  });
  refresh();
})();

// Picking files to add: show how big they are, and a note while they upload.
(() => {
  const form = document.querySelector("[data-upload-form]");
  if (!form) return;
  const input = form.querySelector("[data-upload-files]");
  const note = form.querySelector("[data-upload-size]");
  input.addEventListener("change", () => {
    let total = 0;
    for (const f of input.files) total += f.size;
    const mb = total / 1024 / 1024;
    note.hidden = !input.files.length;
    note.textContent = `${input.files.length} · ${mb >= 1024 ? (mb / 1024).toFixed(1) + " GB" : mb.toFixed(1) + " MB"}`;
  });
  form.addEventListener("submit", () => {
    form.querySelector("[data-upload-wait]").hidden = false;
    form.querySelector("button").disabled = true;
  });
})();

// Phones: the "More" tab opens a sheet with the other pages.
(() => {
  const sheet = document.querySelector("[data-more-sheet]");
  const open = document.querySelector("[data-more-open]");
  if (!sheet || !open) return;
  open.addEventListener("click", () => (sheet.showModal ? sheet.showModal() : sheet.setAttribute("open", "")));
  const close = () => (sheet.close ? sheet.close() : sheet.removeAttribute("open"));
  sheet.querySelector("[data-more-close]").addEventListener("click", close);
  sheet.addEventListener("click", (e) => { if (e.target === sheet) close(); });  // tap outside
})();

// Reminders: "Every day", "Weekdays" and "Weekends" tick the right days.
document.querySelectorAll("[data-days]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const on = btn.dataset.days.split(",");
    btn.closest("form").querySelectorAll('input[name="days"]').forEach((box) => { box.checked = on.includes(box.value); });
  });
});

// Moving inside a course (next lesson, previous, module tasks, next module, a quiz) replaces the page
// instead of adding one, so Back always takes you out to the course, not through every lesson.
// [data-up] links go back when that page is right behind you, so it isn't opened twice.
(() => {
  const path = (u) => { try { const x = new URL(u, location.href); return x.origin === location.origin ? x.pathname : null; } catch (e) { return null; } };
  const goUp = (href) => {
    const want = path(href);
    const nav = window.navigation;
    if (nav && nav.entries && nav.currentEntry) {
      const list = nav.entries(), here = nav.currentEntry.index;
      for (let i = here - 1; i >= 0 && i >= here - 3; i--) {
        if (path(list[i].url) === want) { nav.traverseTo(list[i].key); return; }
      }
    } else if (document.referrer && path(document.referrer) === want && history.length > 1) { history.back(); return; }
    location.href = href;
  };
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest("a[data-replace], a[data-up]");
    if (!a || a.target) return;
    e.preventDefault();
    if (a.hasAttribute("data-up")) goUp(a.href); else location.replace(a.href);
  });
  // Forms marked [data-nav-form] are sent in the background. The server answers with where to go,
  // and the page is replaced, so a sent form never sits behind the Back button.
  document.addEventListener("submit", async (e) => {
    const f = e.target;
    if (!(f instanceof HTMLFormElement) || !f.hasAttribute("data-nav-form") || e.defaultPrevented) return;
    e.preventDefault();
    if (f.dataset.sending) return;
    f.dataset.sending = "1";
    f.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    const body = new FormData(f);
    if (e.submitter && e.submitter.name) body.append(e.submitter.name, e.submitter.value);
    try {
      const r = await fetch(f.action || location.href, { method: "POST", body, headers: { "X-InPace-Nav": "1" } });
      const type = r.headers.get("content-type") || "";
      if (type.includes("application/json")) {
        const data = await r.json();
        if (data && data.go) { goFresh(data.go); return; }
      }
      if (type.includes("text/html")) {  // a page with a message (for example, a mistake in the form)
        const html = await r.text();
        document.open(); document.write(html); document.close();
        return;
      }
      location.reload();
    } catch (err) {
      delete f.dataset.sending;
      f.querySelectorAll("button").forEach((b) => { b.disabled = false; });
      f.removeAttribute("data-nav-form");
      sendForm(f);  // offline or blocked: send it the normal way
    }
  });
})();

// "⋯" menus: only one open at a time; a tap outside or Escape closes it.
(() => {
  const menus = () => document.querySelectorAll("details.menu[open]");
  document.addEventListener("toggle", (e) => {
    const d = e.target;
    if (!(d instanceof HTMLDetailsElement) || !d.classList.contains("menu") || !d.open) return;
    menus().forEach((m) => { if (m !== d) m.open = false; });
  }, true);
  document.addEventListener("click", (e) => {
    menus().forEach((m) => { if (!m.contains(e.target)) m.open = false; });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") menus().forEach((m) => { m.open = false; m.querySelector("summary")?.focus(); });
  });
})();


// Tempo's island: a friend says hello when you tap them.
(() => {
  const say = document.querySelector("[data-friend-say]");
  if (!say) return;
  const lines = JSON.parse(document.getElementById("friend-lines")?.textContent || "{}");
  document.querySelectorAll(".isle-friend").forEach((f) => {
    f.style.cursor = "pointer";
    f.addEventListener("click", () => {
      const k = f.dataset.friend;
      if (!lines[k]) return;
      say.textContent = lines[k];
      say.hidden = false;
      f.classList.remove("hop"); void f.getBoundingClientRect(); f.classList.add("hop");
    });
  });
})();

// The focus trip: count down, grow the plant, plant it on the island when the time is up.
(() => {
  const box = document.querySelector("[data-trip]");
  if (!box || box.hidden) return;
  const goal = +box.dataset.goal, mode = box.dataset.mode;
  let base = +box.dataset.elapsed, t0 = Date.now(), state = box.dataset.state, finishing = false;
  const timeEl = box.querySelector("[data-time]");
  const stones = [...box.querySelectorAll("[data-stone]")];
  const stages = [...box.querySelectorAll(".trip-stage")];
  const note = box.querySelector("[data-paused]");
  const title = document.title;
  const now = () => (state === "running" ? base + (Date.now() - t0) / 1000 : base);
  const fmt = (s) => { s = Math.max(0, Math.ceil(s)); return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); };
  const chime = () => {
    try {
      const a = new (window.AudioContext || window.webkitAudioContext)();
      [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => {
        const o = a.createOscillator(), g = a.createGain();
        o.type = "sine"; o.frequency.value = f; o.connect(g); g.connect(a.destination);
        const t = a.currentTime + i * 0.16;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.2, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
        o.start(t); o.stop(t + 0.65);
      });
    } catch (e) { /* no sound here */ }
  };
  const told = () => { if (window.inpaceTripChanged) window.inpaceTripChanged(); };  // the phone's notification
  const done = () => {
    box.hidden = true;
    told();
    const d = document.querySelector("[data-trip-done]");
    if (d) d.hidden = false;
    document.title = title;
    chime();
    burstConfetti();
  };
  const finish = async () => {
    try {
      const d = await (await fetch("/island/done", { method: "POST" })).json();
      if (d.grown) return done();
      base = d.elapsed; t0 = Date.now();
    } catch (e) { /* try again next tick */ }
    finishing = false;
  };
  const draw = () => {
    const e = now(), p = Math.min(1, e / goal);
    timeEl.textContent = fmt(goal - e);
    if (state === "running") document.title = fmt(goal - e) + " · " + title;
    stones.forEach((s, i) => s.classList.toggle("on", p >= (i + 1) / 10));
    let cur = stages[0];
    stages.forEach((g) => { if (+g.dataset.g <= Math.max(p, 0.05) + 1e-9) cur = g; });
    stages.forEach((g) => { if (g === cur) g.removeAttribute("hidden"); else g.setAttribute("hidden", ""); });
    if (p >= 1 && !finishing) { finishing = true; finish(); }
  };
  setInterval(draw, 1000);
  draw();
  const sync = async () => {
    try {
      const d = await (await fetch("/island/resume", { method: "POST" })).json();
      if (d.grown) return done();
      if (state === "paused" && note) note.hidden = false;
      base = d.elapsed; t0 = Date.now(); state = d.state;
      told();
    } catch (e) { /* offline: keep counting here */ }
  };
  let lock = null;
  const keepAwake = async () => { try { if (mode === "phone" && navigator.wakeLock) lock = await navigator.wakeLock.request("screen"); } catch (e) { lock = null; } };
  keepAwake();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (mode === "phone" && state === "running") {
        base = now(); state = "paused";
        if (navigator.sendBeacon) navigator.sendBeacon("/island/pause"); else fetch("/island/pause", { method: "POST", keepalive: true });
        if (window.inpaceTripPaused) window.inpaceTripPaused();
      }
    } else {
      sync();
      keepAwake();
    }
  });
})();

// ---- Your turtle (v1.17) ----------------------------------------------------------------------------
// The maker recolours a plain Tempo (kept in data-tbase) with the shell, scarf and skin you pick,
// and shows only the thing you chose to wear. "Save a picture" draws the share card as a PNG.
(() => {
  document.querySelectorAll("[data-turtle-maker]").forEach((maker) => {
    let colors;
    try { colors = JSON.parse(maker.querySelector("[data-turtle-colors]").textContent); } catch (e) { return; }
    const pick = (name) => Number((maker.querySelector(`input[name="${name}"]:checked`) || {}).value || 0);
    const recolor = (svg) => {
      const shell = colors.shells[pick("shell")], scarf = colors.scarves[pick("scarf")], skin = colors.skins[pick("skin")];
      const to = [shell[0], shell[1], shell[2], shell[3], scarf[0], scarf[1], skin[0], skin[1], skin[2]];
      // two steps, so one swap can't undo another (same as mascot._recolor)
      colors.base.forEach((from, i) => { if (from !== to[i]) svg = svg.split(from).join(`@@${i}@@`); });
      to.forEach((c, i) => { svg = svg.split(`@@${i}@@`).join(c); });
      return svg;
    };
    const draw = () => {
      maker.querySelectorAll("[data-tbase]").forEach((el) => { el.innerHTML = recolor(el.dataset.tbase); });
      const acc = (maker.querySelector('input[name="acc"]:checked') || {}).value || "none";
      maker.querySelectorAll("[data-turtle-preview] [data-acc]").forEach((g) => { g.toggleAttribute("hidden", g.dataset.acc !== acc); });
    };
    maker.addEventListener("change", draw);
  });

  // "Save a picture of my turtle" and "Share my island": the page draws the SVG as a PNG and sends it back.
  document.querySelectorAll("[data-turtle-png], [data-share-island]").forEach((form) => {
  const src = form.hasAttribute("data-share-island") ? "/island/share.svg" : "/me/turtle.svg";
  form.addEventListener("submit", async (e) => {
    if (form.png.value) return;  // the picture is ready: let the form send it
    e.preventDefault();
    e.stopImmediatePropagation();
    try {
      const svg = await (await fetch(src)).text();
      const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
      const img = new Image();
      await new Promise((ok, bad) => { img.onload = ok; img.onerror = bad; img.src = url; });
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1080;
      canvas.getContext("2d").drawImage(img, 0, 0, 1080, 1080);
      URL.revokeObjectURL(url);
      form.png.value = canvas.toDataURL("image/png");
      form.requestSubmit ? form.requestSubmit() : form.submit();
      setTimeout(() => { form.png.value = ""; }, 1000);
    } catch (err) {
      location.href = src;
    }
  }, true);
  });
})();

// Course page: while the course's videos download, show how far along it is (asks inPace every 1.5 seconds).
(() => {
  const card = document.querySelector("[data-offline]");
  const job = card && card.querySelector("[data-offline-job]");
  if (!job || job.hidden) return;
  const $ = (s) => card.querySelector(s);
  const poll = async () => {
    try {
      const d = await (await fetch(card.dataset.offline, { cache: "no-store" })).json();
      const j = d.job || {};
      if (j.state !== "running") { location.reload(); return; }
      const pct = j.total ? ((j.done + (j.percent || 0) / 100) / j.total) * 100 : 0;
      $("[data-offline-bar]").style.width = pct.toFixed(1) + "%";
      $("[data-offline-num]").textContent = `${j.done} / ${j.total || "…"}`;
      const quick = document.querySelector("[data-offline-quick-num]");  // the small one at the top of the page
      if (quick) quick.textContent = `${j.done} / ${j.total || "…"}`;
      $("[data-offline-now]").textContent = j.title ? `${j.title}${j.percent ? " · " + Math.round(j.percent) + "%" : ""}` : "";
    } catch (e) { /* inPace is busy: try again */ }
    setTimeout(poll, 1500);
  };
  poll();
})();

// Course page: the small links at the top open the "Watch offline" box at the bottom and go there.
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-offline-open]");
  const box = a && document.getElementById("offline");
  if (box && box.tagName === "DETAILS") box.open = true;
});

// Lessons: the "Download this video" button under a YouTube video. It downloads in the background and shows
// how far along it is, right there; when it's saved, one tap plays the copy on this device.
(() => {
  const forms = document.querySelectorAll("form.yt-save[data-yt-save]");
  if (!forms.length) return;
  const show = (f, d) => {
    const btn = f.querySelector("button"), note = f.querySelector("[data-yt-save-note]"), L = f.dataset;
    const busy = d.state === "downloading" || d.state === "waiting";
    f.dataset.state = d.state;
    btn.hidden = busy;
    note.classList.toggle("muted", !busy);
    note.textContent = "";
    if (busy) { const s = document.createElement("span"); s.className = "spin"; s.setAttribute("aria-hidden", "true"); note.append(s); }
    if (d.state === "downloading") note.append(L.lDownloading.replace("{percent}", Math.round(d.percent || 0) + "%"));
    else if (d.state === "waiting") note.append(L.lWaiting);
    else if (d.state === "failed") { note.append(`${L.lFailed} ${d.why || ""}`); btn.querySelector("span").textContent = L.lAgain; }
    else if (d.state === "saved") {
      btn.hidden = true;
      note.append(L.lSaved + " ");
      const play = document.createElement("button");
      play.type = "button"; play.className = "btn small"; play.textContent = "▶ " + L.lPlay;
      play.addEventListener("click", () => location.reload());
      note.append(play);
    }
    return busy;
  };
  const watch = (f) => {
    const poll = async () => {
      let d;
      try { d = (await (await fetch(f.dataset.ytSave, { cache: "no-store" })).json()).video || {}; }
      catch (e) { setTimeout(poll, 3000); return; }  // inPace is busy: ask again a bit later
      if (show(f, d)) setTimeout(poll, 1500);
    };
    poll();
  };
  forms.forEach((f) => {
    if (f.dataset.state === "downloading" || f.dataset.state === "waiting") watch(f);
    f.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const btn = f.querySelector("button"), note = f.querySelector("[data-yt-save-note]");
      btn.disabled = true;
      note.textContent = f.dataset.lStarting;
      try {
        const r = await fetch(f.action, { method: "POST", body: new FormData(f), headers: { Accept: "application/json" } });
        const d = await r.json();
        btn.disabled = false;
        if (!d.ok) { note.textContent = d.message || f.dataset.lFailed; return; }
        if (show(f, d)) watch(f);
      } catch (e) {
        btn.disabled = false;
        note.textContent = f.dataset.lOffline;
      }
    });
  });
})();


// ---- Feels like an app, on every device (v1.23) ---------------------------------------------------------------
// inPace is pages drawn by Python, but it should move like an app:
//  * The main places (Home, My courses, Add, Milestones, the island…) are like tabs: going from one to another
//    replaces the page instead of stacking it, and tapping the one you're on scrolls to the top.
//  * Back closes what's open first (a sheet, a menu, full screen). On a main place it goes Home; on Home it
//    leaves the app (on a phone). Everywhere else it goes one page back, or up to the page it belongs to.
//  * Pages slide in going forward and slide back going back; tabs fade (the CSS reads <html data-nav>).
//  * A thin bar shows at the top when a page takes more than a moment.
(() => {
  const ROOTS = ["/", "/courses", "/roadmaps", "/add", "/milestones", "/island", "/races", "/library", "/people", "/open", "/reminders", "/settings"];
  const clean = (p) => p.replace(/\/+$/, "") || "/";
  const isRoot = (p) => ROOTS.includes(clean(p));
  const here = () => clean(location.pathname);
  const hint = (kind) => { try { sessionStorage.setItem("inpace-nav", kind); } catch (e) { /* private window */ } };
  const busy = () => { clearTimeout(busy.t); busy.t = setTimeout(() => document.documentElement.classList.add("nav-busy"), 180); };
  const idle = () => { clearTimeout(busy.t); document.documentElement.classList.remove("nav-busy"); };
  window.addEventListener("pageshow", idle);
  window.addEventListener("pagehide", idle);

  // Close whatever is open on top of the page. Says whether something was closed.
  const closeTop = () => {
    if (document.fullscreenElement) { document.exitFullscreen(); return true; }
    const dialogs = document.querySelectorAll("dialog[open]");
    if (dialogs.length) { const d = dialogs[dialogs.length - 1]; if (d.close) d.close(); else d.removeAttribute("open"); return true; }
    const open = document.querySelector(".diagram-full [data-d-close], body.diagram-open [data-d-full]");
    if (open) { open.click(); return true; }
    const menu = document.querySelector("details.menu[open], details.course-menu[open]");
    if (menu) { menu.open = false; return true; }
    return false;
  };

  // The one Back for the button at the top, the phone's Back and Alt+←. Returns "handled", or "exit" on Home.
  window.inpaceBack = () => {
    if (closeTop()) return "handled";
    if (here() === "/") return "exit";
    if (isRoot(here())) { hint("back"); busy(); location.replace("/"); return "handled"; }
    const nav = window.navigation;
    const canBack = nav && nav.canGoBack !== undefined ? nav.canGoBack : history.length > 1;
    if (canBack) { history.back(); return "handled"; }
    const up = document.querySelector("a[data-up]");
    hint("back"); busy();
    location.replace(up ? up.href : "/");
    return "handled";
  };

  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest("a[href]");
    if (!a || a.target || a.hasAttribute("download")) return;
    let url;
    try { url = new URL(a.href); } catch (err) { return; }
    if (url.origin !== location.origin) return;
    const tab = a.closest("nav.side, nav.tabbar, .more-sheet, header.top") && isRoot(url.pathname) && !url.search;
    if (tab && clean(url.pathname) === here() && !location.search) {  // the tab you're on: go to the top, with fresh numbers
      e.preventDefault();
      closeTop();
      window.scrollTo({ top: 0, behavior: "smooth" });
      if (window.inpaceRefresh) window.inpaceRefresh();
      return;
    }
    if (tab && isRoot(here())) {  // tab to tab: swap, don't stack
      e.preventDefault();
      hint("tab"); busy();
      location.replace(a.href);
      return;
    }
    if (url.pathname !== location.pathname || url.search !== location.search) busy();
  });
  document.addEventListener("submit", (e) => { if (!e.defaultPrevented && !e.target.closest("form.yt-save")) busy(); });

  // Nothing here is a web page to the person using it: no menu of "Open link in new tab" on a long press or right
  // click, except where it helps (text you typed, text you selected, lesson content, pictures and links in lessons).
  document.addEventListener("contextmenu", (e) => {
    const t = e.target;
    if (t.closest("input, textarea, select, [contenteditable], article, .lesson, pre, code, .player, video, audio")) return;
    if (String(window.getSelection && window.getSelection()).trim()) return;
    e.preventDefault();
  });
  // Links and pictures of the app itself don't drag out like on a web page.
  document.addEventListener("dragstart", (e) => {
    if (e.target.closest && e.target.closest("a, img, svg") && !e.target.closest("article, [draggable=true], .b-les, .b-mod")) e.preventDefault();
  });
})();

// ---- Fresh without reloading (v1.23) ---------------------------------------------------------------------------
// Like a Flutter screen that rebuilds only the widgets whose data changed: a page can mark its main part with
// [data-live]. When you come back to the app (or tap the tab you're on), inPace asks Python for the page again
// and changes only the parts that are different: a progress bar, a number, the next lesson. Nothing blinks, your
// place on the page stays, and open sections stay open. If a changed part needs its script again (a player, a
// folder picker), the page is simply loaded again.
(() => {
  const SCRIPTED = "[data-pick-folder], [data-busy], [data-autosubmit], [data-player], [data-embed], [data-offline], " +
    "[data-yt-save], [data-confetti], [data-search], [data-days], [data-theme-toggle], [data-more-open], script, " +
    "input, textarea, select, video, audio, iframe, canvas";
  const scripted = (n) => n.nodeType === 1 && (n.matches(SCRIPTED) || n.querySelector(SCRIPTED));
  class NeedsReload extends Error {}

  const patch = (a, b) => {
    if (a.isEqualNode(b)) return;
    const same = a.nodeType === 1 && b.nodeType === 1 && a.tagName === b.tagName && a.childNodes.length === b.childNodes.length;
    if (!same) {
      if (scripted(a) || scripted(b)) throw new NeedsReload();
      a.replaceWith(document.importNode(b, true));
      return;
    }
    for (const at of [...a.attributes]) {
      if (!b.hasAttribute(at.name) && !(a.tagName === "DETAILS" && at.name === "open")) a.removeAttribute(at.name);
    }
    for (const at of [...b.attributes]) if (a.getAttribute(at.name) !== at.value) a.setAttribute(at.name, at.value);
    const mine = [...a.childNodes], theirs = [...b.childNodes];
    for (let i = 0; i < mine.length; i++) patch(mine[i], theirs[i]);
  };

  let running = false, last = Date.now();
  const refresh = async () => {
    const live = [...document.querySelectorAll("[data-live][id]")];
    if (!live.length || running || document.hidden) return;
    if (document.querySelector("dialog[open], [data-offline-job]:not([hidden])")) return;  // don't change what's being used
    const el = document.activeElement;
    if (el && /INPUT|TEXTAREA|SELECT/.test(el.tagName)) return;  // typing
    running = true;
    try {
      const r = await fetch(location.pathname + location.search, { cache: "no-store", headers: { "X-InPace-Soft": "1" } });
      if (!r.ok || new URL(r.url).pathname !== location.pathname) return;
      const doc = new DOMParser().parseFromString(await r.text(), "text/html");
      const root = document.documentElement, fresh = doc.documentElement;
      if (root.lang !== fresh.lang || root.dataset.accent !== fresh.dataset.accent) { location.reload(); return; }
      for (const part of live) {
        const next = doc.getElementById(part.id);
        if (next) patch(part, next);
      }
      last = Date.now();
    } catch (e) {
      if (e instanceof NeedsReload) location.reload();  // a part that needs its script changed: load the page again
    } finally {
      running = false;
    }
  };
  window.inpaceRefresh = refresh;
  // Coming back to the app or the window after a while: bring the page up to date, quietly.
  const back = () => { if (Date.now() - last > 20000) refresh(); };
  document.addEventListener("visibilitychange", () => { if (!document.hidden) back(); });
  window.addEventListener("focus", back);
})();

// ---- Make a roadmap (v1.24) ------------------------------------------------------------------------------------
// The path is a list you put in order: add courses from the list below, move them up and down, add a note and
// mark a course optional. It's sent as one hidden field (steps). Without JavaScript the ticked courses are used.
(() => {
  const form = document.querySelector("[data-rm-maker]");
  if (!form) return;
  const L = form.dataset;
  const list = form.querySelector("[data-rm-steps]");
  const empty = form.querySelector("[data-rm-empty]");
  const count = form.querySelector("[data-rm-count]");
  const field = form.querySelector("[data-rm-json]");
  const pick = form.querySelector("[data-rm-pick]");
  const find = form.querySelector("[data-rm-find]");
  const none = form.querySelector("[data-rm-none]");
  const items = pick ? [...pick.querySelectorAll("li[data-id]")] : [];
  form.classList.add("js");
  const icon = (d) => `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const UP = icon('<path d="m6 15 6-6 6 6"/>'), DOWN = icon('<path d="m6 9 6 6 6-6"/>'), X = icon('<path d="M6 6l12 12M18 6 6 18"/>');

  const row = (course, title, note, optional) => {
    const li = document.createElement("li");
    li.className = "rm-edit-step";
    li.dataset.course = course;
    li.innerHTML = `<span class="rm-edit-num"></span>
      <div class="rm-edit-main"><b dir="auto"></b>
        <input class="rm-edit-note" dir="auto" maxlength="400">
        <label class="check small"><input type="checkbox" class="rm-edit-opt"> <span></span></label></div>
      <span class="rm-edit-tools">
        <button type="button" class="btn icon-btn small" data-up>${UP}</button>
        <button type="button" class="btn icon-btn small" data-down>${DOWN}</button>
        <button type="button" class="btn icon-btn small" data-x>${X}</button></span>`;
    li.querySelector("b").textContent = title;
    const n = li.querySelector(".rm-edit-note");
    n.value = note || ""; n.placeholder = L.lNote; n.setAttribute("aria-label", L.lNote);
    li.querySelector(".rm-edit-opt").checked = !!optional;
    li.querySelector(".check span").textContent = L.lOptional;
    li.querySelector("[data-up]").setAttribute("aria-label", L.lUp);
    li.querySelector("[data-down]").setAttribute("aria-label", L.lDown);
    li.querySelector("[data-x]").setAttribute("aria-label", L.lRemove);
    return li;
  };
  // the path as the server drew it becomes editable rows
  [...list.children].forEach((li) => {
    list.replaceChild(row(li.dataset.course, li.dataset.title, li.dataset.note, li.dataset.optional === "1"), li);
  });

  const ids = () => [...list.children].map((li) => li.dataset.course);
  const sync = () => {
    const have = ids();
    [...list.children].forEach((li, i) => {
      li.querySelector(".rm-edit-num").textContent = i + 1;
      li.querySelector("[data-up]").disabled = i === 0;
      li.querySelector("[data-down]").disabled = i === have.length - 1;
    });
    empty.hidden = have.length > 0;
    count.textContent = L.lCount.replace("{n}", have.length);
    items.forEach((it) => {
      const b = it.querySelector("[data-rm-add]");
      const on = have.includes(it.dataset.id);
      b.disabled = on; b.textContent = on ? L.lAdded : L.lAdd;
      it.classList.toggle("added", on);
      it.querySelector("input[type=checkbox]").checked = on;
    });
  };
  list.addEventListener("click", (e) => {
    const li = e.target.closest("li");
    if (!li) return;
    if (e.target.closest("[data-up]") && li.previousElementSibling) list.insertBefore(li, li.previousElementSibling);
    else if (e.target.closest("[data-down]") && li.nextElementSibling) list.insertBefore(li.nextElementSibling, li);
    else if (e.target.closest("[data-x]")) li.remove();
    else return;
    sync();
  });
  items.forEach((it) => {
    const b = it.querySelector("[data-rm-add]");
    b.hidden = false;
    b.addEventListener("click", () => {
      if (ids().includes(it.dataset.id)) return;
      const li = row(it.dataset.id, it.dataset.title, "", false);
      list.appendChild(li);
      sync();
      li.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  });
  if (find) find.addEventListener("input", () => {
    const words = find.value.toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    items.forEach((it) => { const ok = words.every((w) => it.dataset.q.includes(w)); it.hidden = !ok; shown += ok; });
    if (none) none.hidden = shown > 0;
  });
  form.addEventListener("submit", () => {
    field.value = JSON.stringify([...list.children].map((li) => ({
      course: li.dataset.course, note: li.querySelector(".rm-edit-note").value.trim(),
      optional: li.querySelector(".rm-edit-opt").checked })));
  });
  sync();
})();


// Voyage charts (v1.24): a long roadmap scrolls sideways on a phone; start with Tempo's boat in view.
document.querySelectorAll(".voyage-scroll").forEach((box) => {
  const boat = box.querySelector(".voyage-boat");
  if (!boat || box.scrollWidth <= box.clientWidth) return;
  const b = boat.getBoundingClientRect(), r = box.getBoundingClientRect();
  const rtl = getComputedStyle(box).direction === "rtl";
  const want = b.left - r.left + box.scrollLeft - box.clientWidth / 3;
  box.scrollLeft = rtl ? -(box.scrollWidth - box.clientWidth - want) : Math.max(0, want);
});
