// The course builder: the whole course on one page. Parts (modules) hold lessons; each lesson is a video,
// a file, a link or text. Drag to reorder, drop files in, paste YouTube links (with chapter times to cut a long
// video). Every change is sent to /build/save a moment later; the server keeps ids, tasks and progress.
(() => {
  const root = document.getElementById("builder");
  if (!root) return;
  const L = JSON.parse(document.getElementById("b-l10n").textContent);
  const initial = JSON.parse(document.getElementById("b-data").textContent || "null");
  const $ = (id) => document.getElementById(id);
  const state = initial || { cid: "", title: "", description: "", language: document.documentElement.lang === "ar" ? "ar" : "en",
    modules: [{ id: "", title: "", tasks: [], lessons: [] }] };
  let cid = state.cid || "";
  const draft = root.dataset.draft || "";
  const box = $("b-modules");

  // ---- course fields ----
  $("b-title").value = state.title || "";
  $("b-desc").value = state.description || "";
  $("b-lang").value = state.language || "en";
  const folderSel = $("b-folder");
  const newFolderBox = $("b-new-folder-box");
  folderSel.addEventListener("change", () => { newFolderBox.hidden = folderSel.value !== "__new__"; if (folderSel.value !== "__new__") later(); });
  $("b-new-folder").addEventListener("input", later);
  $("b-title").addEventListener("input", () => { state.title = $("b-title").value; later(); });
  $("b-desc").addEventListener("input", () => { state.description = $("b-desc").value; later(); });
  $("b-lang").addEventListener("change", () => { state.language = $("b-lang").value; render(); later(); });
  if (!state.title) $("b-title").focus();

  // ---- helpers ----
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") n.className = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v === true) n.setAttribute(k, "");
      else if (v !== false && v != null) n.setAttribute(k, v);
    }
    kids.flat().forEach((c) => c != null && n.append(c));
    return n;
  };
  const ICON = {
    up: "M6 15l6-6 6 6", down: "M6 9l6 6 6-6", trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13",
    grip: "M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01", note: "M4 6h16M4 12h16M4 18h10",
    link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7L12 6.3M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    file: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5", text: "M5 6h14M5 12h14M5 18h9",
    play: "M8 5v14l11-7z",
  };
  const svg = (name, size = 18) => {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("width", size); s.setAttribute("height", size);
    s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2");
    s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round"); s.setAttribute("aria-hidden", "true");
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path"); p.setAttribute("d", ICON[name]); s.append(p);
    return s;
  };
  const iconBtn = (name, label, fn) => el("button", { type: "button", class: "b-icon", title: label, "aria-label": label, onclick: fn }, svg(name));
  const kindOf = (les) => les.kind || (les.media ? "link" : "text");
  const hasStuff = (les) => (les.title || "").trim() || (les.media || "").trim() || (les.content || "").trim();
  const clock = (s) => { s = Math.floor(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = String(s % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${x}` : `${m}:${x}`; };
  const describe = (media) => {
    const m = /[?&]t=(\d+)(?:&end=(\d+))?/.exec(media || "");
    if (m && /youtu/.test(media)) return `YouTube ${clock(+m[1])}${m[2] ? " → " + clock(+m[2]) : ""}`;
    return media;
  };

  // ---- drawing ----
  let dragged = null;  // {type: "lesson", mi, li} or {type: "module", mi}
  function render() {
    box.replaceChildren(...state.modules.map(drawModule));
    box.dir = state.language === "ar" ? "rtl" : "ltr";
  }
  function drawModule(m, mi) {
    const count = m.lessons.length === 1 ? L.oneLesson : `${m.lessons.length} ${L.lessons}`;
    const tasks = (m.tasks || []).length
      ? el("span", { class: "chip plain small" }, (m.tasks || []).map((t) => t.type === "quiz" ? `${L.quiz} (${t.n})` : null).filter(Boolean).join(" · ") || `${m.tasks.length} ${L.tasks}`)
      : null;
    const title = el("input", { class: "b-mod-title", dir: "auto", value: m.title || "", placeholder: `${L.partTitle} ${mi + 1}`,
      "aria-label": L.partTitle, oninput: (e) => { m.title = e.target.value; later(); } });
    const head = el("div", { class: "b-mod-head" },
      el("span", { class: "b-grip", draggable: "true", title: L.drag, "aria-hidden": "true",
        ondragstart: (e) => { dragged = { type: "module", mi }; e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", "m"); } }, svg("grip")),
      el("span", { class: "b-num" }, String(mi + 1)), title,
      el("span", { class: "muted small b-count" }, count), tasks,
      el("span", { class: "b-tools" },
        iconBtn("up", L.moveUp, () => move(state.modules, mi, -1)),
        iconBtn("down", L.moveDown, () => move(state.modules, mi, 1)),
        iconBtn("trash", L.delete, () => { if (!m.lessons.length || confirm(L.deletePart)) { state.modules.splice(mi, 1); if (!state.modules.length) state.modules.push(newModule()); render(); later(); } })));
    const list = el("ol", { class: "b-lessons" }, m.lessons.map((les, li) => drawLesson(m, mi, les, li)));
    if (!m.lessons.length) list.append(el("li", { class: "b-empty muted small" }, L.emptyPart));
    const sec = el("section", { class: "b-mod card", "data-mi": mi }, head, list, drawAdders(m, mi));
    // dropping a lesson or a part here, or files from the computer
    sec.addEventListener("dragover", (e) => {
      if (dragged || [...(e.dataTransfer.types || [])].includes("Files")) { e.preventDefault(); sec.classList.add("b-over"); }
    });
    sec.addEventListener("dragleave", (e) => { if (!sec.contains(e.relatedTarget)) sec.classList.remove("b-over"); });
    sec.addEventListener("drop", (e) => {
      sec.classList.remove("b-over");
      if (e.dataTransfer.files && e.dataTransfer.files.length && !dragged) { e.preventDefault(); upload(m, e.dataTransfer.files); return; }
      if (!dragged) return;
      e.preventDefault();
      if (dragged.type === "module") { moveTo(state.modules, dragged.mi, mi); }
      else if (!e.target.closest(".b-les")) {  // dropped on the part, not on a lesson: put it at the end
        const [les] = state.modules[dragged.mi].lessons.splice(dragged.li, 1);
        m.lessons.push(les);
      }
      dragged = null; render(); later();
    });
    return sec;
  }
  function drawLesson(m, mi, les, li) {
    const kind = kindOf(les);
    const notes = el("textarea", { class: "b-notes", rows: kind === "text" ? 8 : 3, dir: "auto",
      placeholder: kind === "text" ? L.write : L.notes, oninput: (e) => { les.content = e.target.value; later(); } });
    notes.value = les.content || "";
    const notesBox = el("div", { class: "b-notes-box" }, notes);
    notesBox.hidden = !(kind === "text" || (les.content || "").trim() || les.open);
    const row = el("li", { class: "b-les" + (les.optional ? " is-opt" : ""), draggable: "true", "data-kind": kind },
      el("span", { class: "b-grip", title: L.drag, "aria-hidden": "true" }, svg("grip")),
      el("span", { class: `b-kind k-${kind}` }, L["kind_" + kind] || kind),
      el("span", { class: "b-les-main" },
        el("input", { class: "b-les-title", dir: "auto", value: les.title || "", placeholder: L.lessonTitle, "aria-label": L.lessonTitle,
          oninput: (e) => { les.title = e.target.value; later(); } }),
        les.media ? el("span", { class: "b-media small muted", dir: "ltr", title: les.media }, describe(les.media)) : null),
      el("label", { class: "b-min small muted" },
        el("input", { type: "number", min: "0", max: "999", value: les.minutes || "", "aria-label": L.minutes,
          oninput: (e) => { les.minutes = +e.target.value || 0; later(); } }), L.min),
      el("label", { class: "b-opt small", title: L.optionalHelp },
        el("input", { type: "checkbox", checked: les.optional ? "" : null,
          onchange: (e) => { les.optional = e.target.checked; row.classList.toggle("is-opt", les.optional); later(); } }), L.optional),
      el("span", { class: "b-tools" },
        kind !== "text" ? iconBtn("note", L.notes, () => { les.open = notesBox.hidden; notesBox.hidden = !notesBox.hidden; if (!notesBox.hidden) notes.focus(); }) : null,
        iconBtn("up", L.moveUp, () => moveLesson(mi, li, -1)),
        iconBtn("down", L.moveDown, () => moveLesson(mi, li, 1)),
        iconBtn("trash", L.delete, () => { m.lessons.splice(li, 1); render(); later(); })),
      notesBox);
    row.addEventListener("dragstart", (e) => {
      if (e.target.closest("input, textarea")) { e.preventDefault(); return; }
      dragged = { type: "lesson", mi, li }; e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", "l");
      row.classList.add("b-dragging");
    });
    row.addEventListener("dragend", () => { row.classList.remove("b-dragging"); dragged = null; });
    row.addEventListener("dragover", (e) => { if (dragged && dragged.type === "lesson") { e.preventDefault(); row.classList.add("b-target"); } });
    row.addEventListener("dragleave", () => row.classList.remove("b-target"));
    row.addEventListener("drop", (e) => {
      row.classList.remove("b-target");
      if (!dragged || dragged.type !== "lesson") return;
      e.preventDefault(); e.stopPropagation();
      const from = state.modules[dragged.mi].lessons;
      const [item] = from.splice(dragged.li, 1);
      let at = li;
      if (dragged.mi === mi && dragged.li < li) at -= 1;
      const after = e.clientY > row.getBoundingClientRect().top + row.offsetHeight / 2;
      m.lessons.splice(at + (after ? 1 : 0), 0, item);
      dragged = null; render(); later();
    });
    return row;
  }
  function drawAdders(m, mi) {
    const pick = el("input", { type: "file", multiple: true, hidden: true,
      accept: "video/*,audio/*,.pdf,image/*,.html,.htm,.docx,.pptx,.xlsx,.md,.txt,.py,.js,.ipynb",
      onchange: (e) => { upload(m, e.target.files); e.target.value = ""; } });
    const linkBox = el("div", { class: "b-link-box", hidden: true });
    const area = el("textarea", { rows: 5, dir: "ltr", placeholder: L.linksPlaceholder });
    const fetchBox = el("input", { type: "checkbox", checked: true });
    const status = el("span", { class: "small b-link-status" });
    linkBox.append(area, el("label", { class: "check small" }, fetchBox, " ", L.fetch), el("div", { class: "row" },
      el("button", { type: "button", class: "btn primary small", onclick: async (e) => {
        const btn = e.currentTarget; btn.disabled = true; status.textContent = "";
        try {
          const r = await fetch("/build/links", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: area.value, fetch: fetchBox.checked }) });
          const d = await r.json();
          if (!d.ok) { status.textContent = d.problems.join(" "); btn.disabled = false; return; }
          d.lessons.forEach((x) => m.lessons.push({ id: "", title: x.title, media: x.media, minutes: x.minutes, kind: x.kind, content: "" }));
          render(); later();
        } catch (err) { status.textContent = L.offline; btn.disabled = false; }
      } }, L.add),
      el("button", { type: "button", class: "btn small", onclick: () => { linkBox.hidden = true; } }, L.cancel), status));
    return el("div", { class: "b-adders" },
      el("div", { class: "b-add-row" },
        el("button", { type: "button", class: "b-add", onclick: () => { linkBox.hidden = !linkBox.hidden; if (!linkBox.hidden) area.focus(); } }, svg("play", 20), L.addLink),
        el("button", { type: "button", class: "b-add", onclick: () => pick.click() }, svg("file", 20), L.addFiles),
        el("button", { type: "button", class: "b-add", onclick: () => {
          m.lessons.push({ id: "", title: L.newLesson, media: "", content: "", minutes: 0, kind: "text" });
          render(); later();
          const inputs = box.querySelectorAll(`.b-mod[data-mi="${mi}"] .b-notes`); if (inputs.length) inputs[inputs.length - 1].focus();
        } }, svg("text", 20), L.addText)),
      el("p", { class: "small muted b-drop-hint" }, L.dropHere),
      linkBox, pick, el("div", { class: "b-uploads" }));
  }

  // ---- changes ----
  const newModule = () => ({ id: "", title: "", tasks: [], lessons: [] });
  function move(list, i, step) { const j = i + step; if (j < 0 || j >= list.length) return; [list[i], list[j]] = [list[j], list[i]]; render(); later(); }
  function moveTo(list, from, to) { if (from === to) return; const [x] = list.splice(from, 1); list.splice(to, 0, x); }
  function moveLesson(mi, li, step) {
    const ls = state.modules[mi].lessons, j = li + step;
    if (j >= 0 && j < ls.length) { [ls[li], ls[j]] = [ls[j], ls[li]]; }
    else if (j < 0 && mi > 0) { state.modules[mi - 1].lessons.push(ls.splice(li, 1)[0]); }
    else if (j >= ls.length && mi < state.modules.length - 1) { state.modules[mi + 1].lessons.unshift(ls.splice(li, 1)[0]); }
    render(); later();
  }
  $("b-add-module").addEventListener("click", () => {
    state.modules.push(newModule()); render();
    const t = box.querySelectorAll(".b-mod-title"); t[t.length - 1].focus();
  });

  // ---- files ----
  function upload(m, files) {
    const list = [...files];
    if (!list.length) return;
    const mi = state.modules.indexOf(m);
    const holder = box.querySelector(`.b-mod[data-mi="${mi}"] .b-uploads`);
    const body = new FormData();
    list.forEach((f) => body.append("files", f, f.name));
    if (cid) body.append("cid", cid); else body.append("draft", draft);
    const line = el("p", { class: "small b-progress" }, `${L.uploading} ${list.length > 1 ? list.length + " files" : list[0].name}… 0%`);
    if (holder) holder.append(line);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/build/upload");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) line.textContent = `${L.uploading} ${list.length > 1 ? list.length + " files" : list[0].name}… ${Math.round(e.loaded / e.total * 100)}%`; };
    xhr.onload = () => {
      line.remove();
      let d = null; try { d = JSON.parse(xhr.responseText); } catch (e) {}
      if (!d || !d.ok) { setStatus(L.offline, true); return; }
      const bad = [];
      d.files.forEach((f) => f.ok ? m.lessons.push({ id: "", title: f.title, media: f.media, content: "", minutes: 0, kind: f.kind }) : bad.push(f.problem));
      render(); later();
      if (bad.length) setStatus(bad.join(" "), true);
    };
    xhr.onerror = () => { line.remove(); setStatus(L.offline, true); };
    xhr.send(body);
  }

  // ---- saving ----
  let timer = null, busy = false, again = false;
  function later() { clearTimeout(timer); timer = setTimeout(save, 900); setStatus(L.saving); }
  function setStatus(text, bad) { const s = $("b-status"); s.textContent = text; s.classList.toggle("bad", !!bad); }
  function links() {
    const show = (id, href) => { const a = $(id); a.hidden = !cid; if (cid) a.href = href; };
    show("b-open", `/courses?show=${encodeURIComponent(cid)}`);
    show("b-tasks", `/edit/${encodeURIComponent(cid)}`);
    show("b-text", `/edit/${encodeURIComponent(cid)}/yaml`);
  }
  async function save() {
    if (busy) { again = true; return; }
    const ready = state.title.trim() && state.modules.some((m) => m.lessons.some(hasStuff));
    if (!ready) { setStatus(L.notYet); return; }
    busy = true;
    const payload = { cid, draft, title: state.title, description: state.description, language: state.language,
      modules: state.modules.map((m) => ({ id: m.id, title: m.title,
        lessons: m.lessons.map((l) => ({ id: l.id, title: l.title, media: l.media, content: l.content, minutes: l.minutes,
          optional: !!l.optional })) })) };
    if (folderSel.value === "__new__") payload.new_folder = $("b-new-folder").value;
    else payload.folder = folderSel.value;
    try {
      const r = await fetch("/build/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const d = await r.json();
      if (!d.ok) { setStatus(`${L.problem} ${d.problems.join(" ")}`, true); }
      else {
        const first = !cid;
        cid = d.cid;
        // Give new parts and lessons the ids the server chose (same order, empty ones skipped), keep what's typed.
        const saved = d.data.modules;
        let k = 0;
        state.modules.forEach((m) => {
          const kept = m.lessons.filter(hasStuff);
          if (!kept.length) return;
          const sm = saved[k++];
          if (!sm) return;
          m.id = sm.id; m.tasks = sm.tasks;
          kept.forEach((l, i) => { if (sm.lessons[i]) { l.id = sm.lessons[i].id; l.kind = sm.lessons[i].kind; } });
        });
        if (d.folder && folderSel.value === "__new__") {
          const name = $("b-new-folder").value.trim();
          folderSel.insertBefore(el("option", { value: d.folder }, name), folderSel.lastElementChild);
          folderSel.value = d.folder; newFolderBox.hidden = true;
        }
        if (first) history.replaceState(history.state, "", `/build/${encodeURIComponent(cid)}`);
        setStatus(L.saved);
        links();
      }
    } catch (err) { setStatus(L.offline, true); }
    busy = false;
    if (again) { again = false; save(); }
  }
  window.addEventListener("beforeunload", () => { if (timer) { clearTimeout(timer); save(); } });

  render();
  links();
  if (cid) setStatus(L.saved); else setStatus(L.notYet);
})();
