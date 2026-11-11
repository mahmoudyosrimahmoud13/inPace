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
  const remember = (media, key, getSpeed) => {
    let last = 0;
    const tick = (force, beacon) => {
      if (!media.duration) return;
      if (force || Math.abs(media.currentTime - last) >= 4) {
        last = media.currentTime;
        save(key, media.currentTime, media.duration, getSpeed && getSpeed(), beacon);
      }
    };
    media.addEventListener("timeupdate", () => tick(false));
    media.addEventListener("pause", () => tick(true));
    media.addEventListener("ended", () => save(key, media.duration, media.duration));
    addEventListener("pagehide", () => tick(true, true));
    return tick;
  };
  const resumeAt = (media, start) => {
    if (start > 5) {
      const go = () => { if (media.duration && start < media.duration - 3) media.currentTime = start; };
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
    const toggle = () => (v.paused || v.ended ? v.play() : v.pause());
    const jump = (s) => { v.currentTime = Math.min(Math.max(0, v.currentTime + s), v.duration || 0); say((s > 0 ? "+" : "") + s + "s"); };
    const draw = () => {
      const d = v.duration || 0;
      if (!dragging) seek.value = d ? Math.round((v.currentTime / d) * 1000) : 0;
      seek.style.setProperty("--p", (seek.value / 10) + "%");
      const b = v.buffered.length && d ? v.buffered.end(v.buffered.length - 1) / d * 100 : 0;
      seek.style.setProperty("--b", b + "%");
      time.textContent = `${fmt(v.currentTime)} / ${fmt(d)}`;
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

    const tick = remember(v, L.key, () => speed);
    resumeAt(v, parseFloat(L.resume || "0"));
    v.addEventListener("loadedmetadata", draw);
    v.addEventListener("timeupdate", draw);
    v.addEventListener("progress", draw);
    v.addEventListener("play", state); v.addEventListener("pause", state);
    v.addEventListener("ended", () => { state(); say(L.lEnded); const done = document.querySelector(".lesson-actions, .lesson-foot"); done && done.scrollIntoView({ behavior: "smooth", block: "center" }); });
    v.addEventListener("click", toggle);
    v.addEventListener("dblclick", () => $(".pl-full").click());
    big.addEventListener("click", toggle);
    play.addEventListener("click", toggle);
    $(".pl-back").addEventListener("click", () => jump(-10));
    $(".pl-fwd").addEventListener("click", () => jump(10));
    seek.addEventListener("input", () => { dragging = true; seek.style.setProperty("--p", (seek.value / 10) + "%"); time.textContent = `${fmt((seek.value / 1000) * (v.duration || 0))} / ${fmt(v.duration)}`; });
    seek.addEventListener("change", () => { v.currentTime = (seek.value / 1000) * (v.duration || 0); dragging = false; tick(true); });
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
    restart && restart.addEventListener("click", () => { v.currentTime = 0; v.play(); restart.closest(".resume-hint").remove(); });
    state(); draw(); volState(); wake();
  });
})();
