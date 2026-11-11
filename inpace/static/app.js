// Small helpers only. The app works without JavaScript too.
document.querySelectorAll("[data-autosubmit]").forEach((input) => {
  input.addEventListener("change", () => { if (input.files.length) input.form.submit(); });
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

// Code blocks: language label + copy button.
document.querySelectorAll(".prose pre").forEach((pre) => {
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
(() => {
  const yay = document.querySelector(".yay");
  if (!yay) return;
  const close = () => { yay.classList.add("out"); setTimeout(() => yay.remove(), 300); };
  yay.querySelector(".yay-close").addEventListener("click", close);
  setTimeout(close, 6000);
  if (!yay.hasAttribute("data-confetti") || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const c = document.createElement("canvas");
  c.className = "confetti";
  document.body.appendChild(c);
  const ctx = c.getContext("2d");
  const resize = () => { c.width = innerWidth * devicePixelRatio; c.height = innerHeight * devicePixelRatio; };
  resize();
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
})();

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
      el.src = box.dataset.embed;
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
  });
});

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
      location.href = r.url || location.href;
    };
    rec.start(1000);
    started = Date.now();
    btn.classList.add("recording");
    btn.textContent = "■ " + L.lStop;
    timer = setInterval(() => (time.textContent = fmt(Math.round((Date.now() - started) / 1000))), 500);
  });
});
