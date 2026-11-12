// Small helpers only. The app works without JavaScript too.
document.querySelectorAll("[data-autosubmit]").forEach((input) => {
  input.addEventListener("change", () => {
    if (input.tagName === "SELECT") return;  // handled below
    if (input.type === "file" ? input.files.length : true) input.form.submit();
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
    // Keep the keyboard keys working after a click (the big button disappears once it's pressed).
    box.addEventListener("click", (e) => { if (e.target.tagName !== "INPUT") box.focus({ preventScroll: true }); });
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
document.querySelectorAll("select[data-autosubmit]").forEach((s) => s.addEventListener("change", () => s.value && s.form.submit()));

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
  const visible = (el) => el && el.offsetParent !== null && el.getBoundingClientRect().width > 0;
  const finish = () => {
    fetch("/tour/done", { method: "POST" }).catch(() => {});
    [shade, spot, card].forEach((x) => x.remove());
    document.removeEventListener("keydown", keys);
    if (location.search.includes("tour=1")) history.replaceState(null, "", location.pathname);
  };
  const place = () => {
    const s = steps[i];
    // A target can list a few places ("the sidebar link, or the phone tab"): use the first one on screen.
    const el = s.target && s.target.split(",").map((t) => document.querySelector(t.trim())).find(visible);
    card.classList.remove("center");
    if (visible(el)) {
      el.scrollIntoView({ block: "nearest" });
      const r = el.getBoundingClientRect(), pad = 6;
      Object.assign(spot.style, { display: "block", top: r.top - pad + "px", left: r.left - pad + "px",
        width: r.width + pad * 2 + "px", height: r.height + pad * 2 + "px" });
      shade.classList.add("clear");
      const cw = Math.min(380, innerWidth - 32), ch = card.offsetHeight;
      let left = r.right + 18, top = Math.max(16, Math.min(r.top - 20, innerHeight - ch - 16));
      if (left + cw > innerWidth - 16) left = r.left - cw - 18;              // no room on the right
      if (left < 16) { left = Math.max(16, Math.min(r.left, innerWidth - cw - 16)); top = r.bottom + 14; } // below
      if (top + ch > innerHeight - 16) top = Math.max(16, r.top - ch - 14);   // above
      Object.assign(card.style, { left: left + "px", top: top + "px", width: cw + "px" });
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
      if (a) { e.preventDefault(); location.href = a.href; }
    }
  });
})();

// Back and forward: the app window has no browser buttons, so inPace has its own (top left),
// plus Alt+← / Alt+→ and the side buttons on a mouse.
(() => {
  const back = document.querySelector("[data-nav-back]"), fwd = document.querySelector("[data-nav-fwd]");
  if (!back) return;
  const goBack = () => (history.length > 1 ? history.back() : (location.pathname !== "/" && (location.href = "/")));
  const goFwd = () => history.forward();
  back.addEventListener("click", goBack);
  fwd.addEventListener("click", goFwd);
  // Show which way you can go, where the window can tell.
  const nav = window.navigation;
  const sync = () => {
    if (!nav || nav.canGoBack === undefined) return;
    back.disabled = !nav.canGoBack && location.pathname === "/";
    fwd.disabled = !nav.canGoForward;
  };
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
  const run = () => {
    const words = box.value.toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    cards.forEach((c) => {
      const ok = words.every((w) => c.dataset.courseSearch.includes(w));
      c.hidden = !ok;
      shown += ok;
    });
    if (none) none.hidden = shown > 0;
  };
  box.addEventListener("input", run);
  if (box.value) run();  // opened from a shared link: show that course
})();

// ---- Android app ---------------------------------------------------------------------------------
// In the Android app there is no browser, so downloads, folder picking and sharing go through the app
// (window.InPaceAndroid, provided by the Flutter shell).
(() => {
  const bridge = window.InPaceAndroid;
  if (!bridge) return;
  document.documentElement.classList.add("android");
  const send = (msg) => bridge.postMessage(JSON.stringify(msg));
  const DOWNLOADS = /^\/(courses\/[^/]+\/(export|publish\/file)|milestones\/[^/]+\/(export|files|record)|people\/card|outbox\/|files\/[0-9a-f]{64}$|races\/[^/]+\/(invite|update)$)/;

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
    if (!form.matches('form[action="/settings/backup"]')) return;
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
