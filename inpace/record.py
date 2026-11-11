"""A shareable learning record: one HTML file that checks itself, offline, in any browser."""
from __future__ import annotations

import html
import json

from .canon import now_utc
from .vault import Vault, display_name


def build_record(v: Vault, journey: str) -> str:
    j = v.journey(journey)
    course = v.get_course(j["course_id"])
    ms = v.milestones(journey)
    approvals, checkers = [], {}
    for m in ms:
        for a in m["approvals"]:
            approvals.append({"kind": "decision", "milestone": a["milestone"], "journey": journey,
                              "learner": v.identity.id, "checker": a["checker"], "decision": a["decision"],
                              "note": a["note"], "at": a["at"], "sig": a["sig"]})
            p = v.person(a["checker"])
            checkers[a["checker"]] = display_name(p) if p else "A checker"
    data = {"learner": v.me, "course": {"title": course.title, "id": course.id},
            "milestones": [{"body": m["body"], "hash": m["hash"], "sig": m["sig"]} for m in ms],
            "approvals": approvals, "checkers": checkers, "made": now_utc()}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = f"{v.me['name']} · {course.title}"
    return TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__DATA__", payload)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · inPace learning record</title>
<style>
:root{--bg:#F7F7F4;--s:#fff;--l:#E4E4DC;--i:#15191F;--m:#5F656D;--g:#1B6E4D;--gb:#E6F2EB;--b:#A8261D;--bb:#FBE7E4;--w:#8A4E0E;--wb:#FBEFDF;--p:#233953}
@media (prefers-color-scheme:dark){:root{--bg:#0F1113;--s:#181B1F;--l:#2A2F35;--i:#ECEFF3;--m:#969DA6;--g:#7DD3A8;--gb:rgba(125,211,168,.12);--b:#FF9E94;--bb:rgba(255,158,148,.12);--w:#F2B56E;--wb:rgba(242,181,110,.12);--p:#C9DAF0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--i);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:820px;margin:0 auto;padding:2.5rem 1rem 4rem}h1{font-family:Georgia,serif;font-weight:500;font-size:2.1rem;margin:.2rem 0}
.eyebrow{font-size:.75rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--m)}
.card{background:var(--s);border:1px solid var(--l);border-radius:12px;padding:1.25rem 1.4rem;margin:1rem 0}
.bar{height:8px;background:var(--l);border-radius:9px;overflow:hidden}.bar span{display:block;height:100%;background:var(--g)}
.row{display:flex;gap:.6rem;flex-wrap:wrap;align-items:center;justify-content:space-between}
.chip{font-size:.78rem;font-weight:700;border-radius:99px;padding:.2rem .7rem;background:var(--l)}.good{background:var(--gb);color:var(--g)}.bad{background:var(--bb);color:var(--b)}.warn{background:var(--wb);color:var(--w)}
button{font:inherit;font-weight:700;padding:.7rem 1.3rem;border-radius:8px;border:0;background:var(--p);color:var(--bg);cursor:pointer}
ol{list-style:none;padding:0;margin:0}li{padding:.8rem 0;border-top:1px solid var(--l)}li:first-child{border-top:0}
.m{color:var(--m);font-size:.88rem}#result{display:none}code{font-size:.8rem;word-break:break-all}
</style>
</head>
<body>
<main>
  <p class="eyebrow">Learning record · made with inPace</p>
  <h1 id="title"></h1>
  <p class="m" id="sub"></p>
  <div class="card">
    <div class="row"><b id="pct"></b><span class="m" id="mods"></span></div>
    <div class="bar" style="margin-top:.6rem"><span id="barfill"></span></div>
  </div>
  <div class="card">
    <div class="row"><div><b>Is this record real?</b><br><span class="m">Checks every fingerprint and signature, right here in your browser. Nothing is sent anywhere.</span></div>
    <button id="verify">Verify this record</button></div>
    <div id="result" class="card"></div>
  </div>
  <h2 style="font-family:Georgia,serif;font-weight:500">Milestones</h2>
  <div class="card"><ol id="list"></ol></div>
  <p class="m">What this proves: the steps were followed in order, the work existed, the history wasn't changed, and the checkers named here approved it. It can't prove how well someone learned.</p>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const last = D.milestones.length ? D.milestones[D.milestones.length - 1].body.summary : null;
$("title").textContent = D.learner.name + " · " + D.course.title;
$("sub").textContent = D.milestones.length + " milestones · record made " + D.made.slice(0, 10);
$("pct").textContent = (last ? last.percent : 0) + "% of the course";
$("mods").textContent = last ? last.modules_done + " of " + last.modules_total + " modules" : "";
$("barfill").style.width = (last ? last.percent : 0) + "%";
const byM = {};
D.approvals.forEach((a) => (byM[a.milestone] = byM[a.milestone] || []).push(a));
$("list").innerHTML = D.milestones.slice().reverse().map((m) => {
  const b = m.body, as = byM[m.hash] || [];
  const ok = as.filter((a) => a.decision === "approved");
  const chip = ok.length ? `<span class="chip good">Approved by ${esc(ok.map((a) => D.checkers[a.checker]).join(", "))}</span>`
                         : `<span class="chip">Not approved yet</span>`;
  return `<li><div class="row"><b>Milestone ${b.seq}</b><span class="m">${esc(b.created_at.slice(0, 10))}</span></div>
    <div class="row"><span class="m">${b.summary.percent}% · ${b.summary.lessons_done} lessons done</span>${chip}</div></li>`;
}).join("");

// Same canonical form as inPace (SPEC.md section 1).
function norm(v) {
  if (typeof v === "string") return v.replace(/\r\n/g, "\n").replace(/\r/g, "\n").normalize("NFC");
  if (Array.isArray(v)) return v.map(norm);
  if (v && typeof v === "object") { const o = {}; Object.keys(v).sort().forEach((k) => (o[k] = norm(v[k]))); return o; }
  return v;
}
const canon = (v) => new TextEncoder().encode(JSON.stringify(norm(v)));
const hex = (buf) => [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, "0")).join("");
const unhex = (h) => new Uint8Array(h.match(/../g).map((x) => parseInt(x, 16)));
async function sha(v) { return hex(await crypto.subtle.digest("SHA-256", canon(v))); }
async function sigOk(pub, data, sig) {
  const key = await crypto.subtle.importKey("raw", unhex(pub), { name: "Ed25519" }, false, ["verify"]);
  return crypto.subtle.verify({ name: "Ed25519" }, key, unhex(sig), canon(data));
}
$("verify").onclick = async () => {
  const out = $("result"), problems = [];
  let sigs = true;
  try { await crypto.subtle.importKey("raw", new Uint8Array(32), { name: "Ed25519" }, false, ["verify"]); }
  catch (e) { sigs = false; }
  let prev = "";
  for (const [i, m] of D.milestones.entries()) {
    const b = m.body;
    if (b.seq !== i + 1) { problems.push(`Milestone ${i + 1} is missing or out of order.`); break; }
    if (await sha(b) !== m.hash) { problems.push(`Milestone ${b.seq} was changed after it was saved.`); break; }
    if (b.prev !== prev) { problems.push(`Milestone ${b.seq} doesn't connect to the one before.`); break; }
    if (b.learner !== D.learner.id) { problems.push(`Milestone ${b.seq} belongs to someone else.`); break; }
    if (sigs && !(await sigOk(D.learner.id, { kind: "milestone", hash: m.hash }, m.sig))) { problems.push(`Milestone ${b.seq} isn't signed by ${D.learner.name}.`); break; }
    prev = m.hash;
  }
  if (sigs) for (const a of D.approvals) {
    const { sig, ...rest } = a;
    if (!(await sigOk(a.checker, rest, sig))) problems.push(`An approval from ${D.checkers[a.checker]} isn't genuine.`);
  }
  out.style.display = "block";
  if (problems.length) { out.className = "card bad"; out.innerHTML = "<b>This record has problems</b><ul>" + problems.map((p) => `<li>${esc(p)}</li>`).join("") + "</ul>"; }
  else {
    out.className = "card good";
    out.innerHTML = `<b>✓ This record checks out</b><br>All ${D.milestones.length} milestones are intact and connected` +
      (sigs ? `, signed by ${esc(D.learner.name)}, and every approval is genuine.` : `. (This browser can't check signatures; try a recent Chrome, Edge, Firefox or Safari.)`) +
      `<details style="margin-top:.5rem"><summary class="m">Show keys</summary><p class="m">Learner: <code>${D.learner.id}</code></p>` +
      Object.entries(D.checkers).map(([k, n]) => `<p class="m">${esc(n)}: <code>${k}</code></p>`).join("") + `</details>`;
  }
};
</script>
</body>
</html>
"""
