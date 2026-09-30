/* CodeSync AI front end. Plain JavaScript, no external files, works offline. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const inline = (s) => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>");
  const fmt = (s) => {
    s = Math.max(0, Math.floor(s || 0));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  };
  const load = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage may be off */ } };

  const state = {
    lesson: null,
    lang: "en",
    links: [],            // per editor line: {time, text} or null
    prevCount: 1,
    activeSeg: -1,
    activeSlide: -1,
    shownCp: {},          // checkpoint index -> true once its card was shown
    passedCp: {},
    cp: null,             // active checkpoint index
    hintLevel: 0,
    crop: null,           // {x0,y0,x1,y1} as fractions of the video frame
    capture: null,        // last capture result
    engine: load("cs.engine", "auto"),
    low: load("cs.low", false),
    hw: null,
  };

  const video = $("video"), code = $("code");
  const out = $("out");

  /* ---------- api ---------- */
  async function api(path, body, form) {
    const opt = form ? { method: "POST", body: form } :
      body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
    const r = await fetch(path, opt);
    if (!r.ok) {
      let msg = r.statusText;
      try { const j = await r.json(); msg = j.detail || msg; } catch (e) { /* not json */ }
      throw new Error(msg);
    }
    return r.json();
  }
  const showError = (e) => { out.innerHTML = `<p class="err">${esc(e.message || e)}</p>`; };

  function seek(t, play = true) {
    video.currentTime = t;
    if (play) video.play().catch(() => {});
  }

  /* ---------- lesson rendering ---------- */
  function renderTranscript() {
    const l = state.lesson;
    $("transcript").innerHTML = l.transcript.map((s, i) => {
      const text = state.lang === "hi" && s.text_hi ? s.text_hi : s.text;
      return `<li data-i="${i}" ${state.lang === "hi" ? 'lang="hi"' : ""}><span class="t">${fmt(s.start)}</span><span>${inline(text)}</span></li>`;
    }).join("");
    state.activeSeg = -1;
    onTime();
  }

  function showSlide(i) {
    const slides = state.lesson.slides;
    if (!slides.length) return;
    i = Math.min(Math.max(i, 0), slides.length - 1);
    state.activeSlide = i;
    $("slideImg").src = `/lessons/${state.lesson.id}/${slides[i].img}`;
    $("slideImg").alt = slides[i].title;
    $("slideCount").textContent = `Slide ${i + 1} of ${slides.length}`;
  }

  function onTime() {
    const l = state.lesson;
    if (!l) return;
    const t = video.currentTime || 0;
    $("clock").textContent = `${fmt(t)} / ${fmt(video.duration || l.duration)}`;

    let seg = -1;
    l.transcript.forEach((s, i) => { if (t >= s.start && t < s.end) seg = i; });
    if (seg !== state.activeSeg) {
      const items = $("transcript").children;
      if (items[state.activeSeg]) items[state.activeSeg].classList.remove("now");
      if (items[seg]) {
        items[seg].classList.add("now");
        if (!$("pane-transcript").hidden) items[seg].scrollIntoView?.({ block: "nearest" });
      }
      state.activeSeg = seg;
    }

    let slide = 0;
    l.slides.forEach((s, i) => { if (t >= s.time) slide = i; });
    if ($("slideSync").checked && slide !== state.activeSlide) showSlide(slide);

    let ch = "";
    l.chapters.forEach((c) => { if (t >= c.time) ch = c.title; });
    $("chapter").textContent = ch;

    (l.checkpoints || []).forEach((cp, i) => {
      if (!state.shownCp[i] && t >= cp.time && t < cp.time + 1.5 && !video.paused) {
        video.pause();
        showCheckpoint(i);
      }
    });
  }

  /* ---------- tabs ---------- */
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => selectTab(b.dataset.tab)));
  function selectTab(name) {
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
    ["transcript", "slides", "search", "notes"].forEach((n) => { $("pane-" + n).hidden = n !== name; });
    if (name === "search") $("searchInput").focus();
  }

  $("transcript").addEventListener("click", (e) => {
    const li = e.target.closest("li");
    if (li) seek(state.lesson.transcript[+li.dataset.i].start);
  });
  $("slidePrev").addEventListener("click", () => { $("slideSync").checked = false; showSlide(state.activeSlide - 1); });
  $("slideNext").addEventListener("click", () => { $("slideSync").checked = false; showSlide(state.activeSlide + 1); });
  $("slideImg").addEventListener("click", () => { const s = state.lesson.slides[state.activeSlide]; if (s) seek(s.time); });
  $("langEn").addEventListener("click", () => setLang("en"));
  $("langHi").addEventListener("click", () => setLang("hi"));
  function setLang(l) {
    state.lang = l;
    $("langEn").classList.toggle("on", l === "en");
    $("langHi").classList.toggle("on", l === "hi");
    renderTranscript();
  }

  /* ---------- search ---------- */
  async function doSearch() {
    const q = $("searchInput").value.trim();
    if (!q) return;
    try {
      const rows = await api("/api/search", { lesson: state.lesson.id, q });
      const label = { transcript: "Video", slide: "Slide", code: "Teacher's code" };
      $("searchResults").innerHTML = rows.length ? rows.map((r) =>
        `<li data-t="${r.time}" data-src="${r.source}"><span class="src">${label[r.source]}</span><span>${fmt(r.time)}</span>` +
        (r.source === "code" ? `<span class="code-line">${esc(r.text)}</span>` : `<span>${inline(r.text)}</span>`) + "</li>"
      ).join("") : '<li class="muted">Nothing matched. Try other words.</li>';
    } catch (e) { $("searchResults").innerHTML = `<li class="err">${esc(e.message)}</li>`; }
  }
  $("searchBtn").addEventListener("click", doSearch);
  $("searchInput").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
  $("searchResults").addEventListener("click", (e) => {
    const li = e.target.closest("li[data-t]");
    if (!li) return;
    seek(parseFloat(li.dataset.t));
    if (li.dataset.src === "slide") { $("slideSync").checked = true; selectTab("slides"); }
  });

  /* ---------- notes ---------- */
  const notesKey = () => "cs.notes." + state.lesson.id;
  function renderNotes() {
    const notes = load(notesKey(), []).sort((a, b) => a.t - b.t);
    $("noteList").innerHTML = notes.length ? notes.map((n, i) =>
      `<li class="note" data-t="${n.t}"><span>${fmt(n.t)}</span><span>${esc(n.text)}</span><button class="btn" data-del="${i}" type="button">Remove</button></li>`
    ).join("") : '<li class="muted">No notes yet. Notes are saved on this laptop.</li>';
  }
  $("noteBtn").addEventListener("click", () => {
    const text = $("noteInput").value.trim();
    if (!text) return;
    const notes = load(notesKey(), []);
    notes.push({ t: Math.floor(video.currentTime || 0), text });
    save(notesKey(), notes);
    $("noteInput").value = "";
    renderNotes();
  });
  $("noteList").addEventListener("click", (e) => {
    const del = e.target.closest("[data-del]");
    if (del) {
      const notes = load(notesKey(), []).sort((a, b) => a.t - b.t);
      notes.splice(+del.dataset.del, 1);
      save(notesKey(), notes);
      return renderNotes();
    }
    const li = e.target.closest("li[data-t]");
    if (li) seek(parseFloat(li.dataset.t));
  });

  /* ---------- editor with video-linked lines ---------- */
  const hInner = document.createElement("div"); hInner.className = "hlayer-inner";
  const gInner = document.createElement("div"); gInner.className = "gutter-inner";
  $("hlayer").appendChild(hInner);
  $("gutter").appendChild(gInner);
  const lines = () => code.value.split("\n");

  function renderEditor() {
    const ls = lines();
    while (state.links.length < ls.length) state.links.push(null);
    state.links.length = ls.length;
    hInner.innerHTML = ls.map((text, i) => {
      const L = state.links[i];
      return `<div class="hrow${L ? " linked" + (L.text !== text ? " edited" : "") : ""}"></div>`;
    }).join("");
    gInner.innerHTML = ls.map((_, i) => {
      const L = state.links[i];
      return `<div class="grow"><span>${i + 1}</span>` +
        (L ? `<button type="button" data-t="${L.time}" title="Jump to ${fmt(L.time)} in the video">${fmt(L.time)}</button>` : "") + "</div>";
    }).join("");
    syncScroll();
  }
  function syncScroll() {
    const y = -code.scrollTop;
    hInner.style.transform = gInner.style.transform = `translateY(${y}px)`;
  }
  const caretLine = () => code.value.slice(0, code.selectionStart).split("\n").length - 1;

  code.addEventListener("input", () => {
    const ls = lines();
    const d = ls.length - state.prevCount;
    if (d !== 0) {
      const cl = caretLine();
      if (d > 0) {
        const col = code.selectionStart - code.value.lastIndexOf("\n", code.selectionStart - 1) - 1;
        // Enter pressed at the start of a line: the empty line is new, the old line (and its link) moves down
        const at = d === 1 && col === 0 && cl > 0 && ls[cl - 1] === "" ? cl - 1 : Math.max(0, cl - d + 1);
        state.links.splice(at, 0, ...Array(d).fill(null));
      } else {
        state.links.splice(cl + 1, -d);
      }
    }
    state.prevCount = ls.length;
    renderEditor();
  });
  code.addEventListener("scroll", syncScroll);
  code.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      if (!document.execCommand || !document.execCommand("insertText", false, "    ")) {
        const s = code.selectionStart;
        code.setRangeText("    ", s, code.selectionEnd, "end");
        code.dispatchEvent(new Event("input"));
      }
    } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      runCode();
    }
  });
  gInner.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-t]");
    if (b) seek(parseFloat(b.dataset.t));
  });

  function setEditor(text, links) {
    code.value = text;
    state.links = links || [];
    state.prevCount = lines().length;
    renderEditor();
  }
  function insertLines(newLines, newLinks) {
    if (code.value.trim() === "") return setEditor(newLines.join("\n"), newLinks);
    const ls = lines();
    const at = Math.min(caretLine() + 1, ls.length);
    ls.splice(at, 0, ...newLines);
    state.links.splice(at, 0, ...newLinks);
    code.value = ls.join("\n");
    state.prevCount = ls.length;
    renderEditor();
  }

  /* ---------- code from video: crop + capture ---------- */
  const layer = $("cropLayer"), box = $("cropBox");
  function videoRect() {
    const W = video.clientWidth, H = video.clientHeight, vw = video.videoWidth, vh = video.videoHeight;
    if (!vw) return { x: 0, y: 0, w: W, h: H };
    const s = Math.min(W / vw, H / vh), w = vw * s, h = vh * s;
    return { x: (W - w) / 2, y: (H - h) / 2, w, h };
  }
  function drawCrop() {
    if (!state.crop) return;
    const r = videoRect(), c = state.crop;
    Object.assign(box.style, {
      left: r.x + c.x0 * r.w + "px", top: r.y + c.y0 * r.h + "px",
      width: (c.x1 - c.x0) * r.w + "px", height: (c.y1 - c.y0) * r.h + "px",
    });
  }
  function enterCapture() {
    video.pause();
    const d = state.lesson.capture_crop || [0, 0, 1, 1];
    state.crop = { x0: d[0], y0: d[1], x1: d[2], y1: d[3] };
    layer.hidden = false;
    drawCrop();
  }
  function exitCapture() { layer.hidden = true; }
  let drag = null;
  layer.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".crop-bar")) return;
    const r = videoRect(), b = layer.getBoundingClientRect();
    const fx = Math.min(1, Math.max(0, (e.clientX - b.left - r.x) / r.w));
    const fy = Math.min(1, Math.max(0, (e.clientY - b.top - r.y) / r.h));
    drag = { fx, fy };
    state.crop = { x0: fx, y0: fy, x1: fx, y1: fy };
    layer.setPointerCapture(e.pointerId);
    drawCrop();
  });
  layer.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const r = videoRect(), b = layer.getBoundingClientRect();
    const fx = Math.min(1, Math.max(0, (e.clientX - b.left - r.x) / r.w));
    const fy = Math.min(1, Math.max(0, (e.clientY - b.top - r.y) / r.h));
    state.crop = { x0: Math.min(drag.fx, fx), y0: Math.min(drag.fy, fy), x1: Math.max(drag.fx, fx), y1: Math.max(drag.fy, fy) };
    drawCrop();
  });
  layer.addEventListener("pointerup", () => { drag = null; });
  window.addEventListener("resize", drawCrop);
  $("captureBtn").addEventListener("click", enterCapture);
  $("cropCancel").addEventListener("click", exitCapture);
  $("cropGo").addEventListener("click", doCapture);

  async function doCapture() {
    const c = state.crop;
    if (!c || c.x1 - c.x0 < 0.02 || c.y1 - c.y0 < 0.02) { $("cropHint").textContent = "Drag a larger box around the code."; return; }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const t = video.currentTime;
    $("cropGo").disabled = true;
    out.innerHTML = '<p class="muted">Reading the frame on this laptop…</p>';
    canvas.toBlob(async (blob) => {
      try {
        const f = new FormData();
        f.append("file", blob, "frame.png");
        f.append("lesson", state.lesson.id);
        f.append("t", t);
        f.append("crop", [c.x0, c.y0, c.x1, c.y1].join(","));
        f.append("engine", state.engine);
        f.append("low_resource", state.low);
        const res = await api("/api/capture", null, f);
        state.capture = { res, t };
        exitCapture();
        showSheet(res, t);
        out.innerHTML = '<p class="muted">Check the captured code, then add it to your editor.</p>';
        refreshHardware();
      } catch (e) { showError(e); }
      finally { $("cropGo").disabled = false; }
    }, "image/png");
  }

  function showSheet(res, t) {
    const n = res.lines.filter((l) => !l.blank).length;
    $("sheetTitle").textContent = `Code from ${fmt(t)}`;
    $("sheetMeta").textContent = `${n} lines read in ${(res.ocr_ms / 1000).toFixed(1)} s on the ${res.engine === "npu" ? "NPU" : "CPU"}`;
    $("sheetCode").value = res.code;
    const fixes = res.lines.flatMap((l) => l.fixes || []);
    const shaky = res.lines.map((l, i) => ({ l, i })).filter((x) => !x.l.blank && x.l.conf < 0.9);
    let html = "";
    if (fixes.length) html += "Corrected using the lesson's words: " + fixes.map(([a, b]) => `<b>${esc(a)}</b> to <b>${esc(b)}</b>`).join(", ") + ". ";
    if (shaky.length) html += "Double-check line " + shaky.map((x) => x.i + 1).join(", ") + ": the reader was less sure.";
    $("sheetFixes").innerHTML = html;
    $("captureSheet").hidden = false;
  }
  function sheetLines() {
    const { res, t } = state.capture;
    const text = $("sheetCode").value.replace(/\s+$/, "");
    const ls = text.split("\n");
    const same = ls.length === res.lines.length;
    const links = ls.map((s, i) => {
      if (!s.trim()) return null;
      const src = same ? res.lines[i] : null;
      return { time: src && src.time != null ? src.time : t, text: s };
    });
    return { ls, links };
  }
  $("sheetAdd").addEventListener("click", () => { const { ls, links } = sheetLines(); insertLines(ls, links); $("captureSheet").hidden = true; code.focus(); });
  $("sheetReplace").addEventListener("click", () => { const { ls, links } = sheetLines(); setEditor(ls.join("\n"), links); $("captureSheet").hidden = true; code.focus(); });
  $("sheetClose").addEventListener("click", () => { $("captureSheet").hidden = true; });

  /* ---------- run, explain, checkpoints, hints ---------- */
  function explainHtml(info) {
    if (!info) return "";
    const rel = (info.related || []).filter((r) => r.source !== "code").map((r) =>
      `<div class="jump"><button class="btn" data-jump="${r.time}" type="button">Watch ${fmt(r.time)}</button> <span class="muted">${inline(r.text)}</span></div>`).join("");
    return `<div class="card"><strong>${esc(info.type)}</strong>${info.message ? ": " + esc(info.message) : ""}<p>${esc(info.explanation)}</p>${rel}</div>`;
  }
  async function runCode() {
    $("runBtn").disabled = true;
    try {
      const r = await api("/api/run", { code: code.value, lesson: state.lesson.id });
      out.innerHTML = (r.stdout ? `<pre>${esc(r.stdout)}</pre>` : "") +
        (r.stderr ? `<pre class="err">${esc(r.stderr)}</pre>` : "") +
        (!r.stdout && !r.stderr ? '<p class="muted">The program ran and printed nothing.</p>' : "") + explainHtml(r.explain);
    } catch (e) { showError(e); }
    $("runBtn").disabled = false;
  }
  $("runBtn").addEventListener("click", runCode);
  out.addEventListener("click", (e) => {
    const j = e.target.closest("[data-jump]");
    if (j) return seek(parseFloat(j.dataset.jump));
    if (e.target.id === "loadStarter") {
      const cp = state.lesson.checkpoints[state.cp];
      const ls = cp.starter.replace(/\s+$/, "").split("\n");
      insertLines(ls, ls.map(() => null));
      code.focus();
    } else if (e.target.id === "resumeVideo") video.play().catch(() => {});
  });

  function showCheckpoint(i) {
    const cp = state.lesson.checkpoints[i];
    state.cp = i; state.shownCp[i] = true; state.hintLevel = 0;
    $("checkBtn").hidden = false; $("hintBtn").hidden = false;
    $("hintBtn").textContent = "Give me a hint"; $("hintBtn").disabled = false;
    out.innerHTML = `<div class="card hint"><strong>Checkpoint: ${esc(cp.title)}</strong><p>${esc(cp.prompt)}</p>` +
      '<button id="loadStarter" class="btn" type="button">Put starter code in the editor</button> ' +
      '<button id="resumeVideo" class="btn" type="button">Keep watching</button></div><div id="hints"></div>';
  }
  $("hintBtn").addEventListener("click", () => {
    const cp = state.lesson.checkpoints[state.cp];
    if (!cp) return;
    const h = cp.hints[state.hintLevel];
    if (!h) return;
    const holder = $("hints") || out;
    const body = h.level === 3 ? `<pre>${esc(h.text)}</pre>` : `<p>${esc(h.text)}</p>`;
    const jump = h.jump != null ? `<button class="btn" data-jump="${h.jump}" type="button">Watch ${fmt(h.jump)}</button>` : "";
    holder.insertAdjacentHTML("beforeend", `<div class="card hint"><strong>${["", "A nudge", "A bigger hint", "The solution"][h.level]}</strong>${body}${jump}</div>`);
    state.hintLevel++;
    const next = cp.hints[state.hintLevel];
    if (!next) $("hintBtn").disabled = true;
    else $("hintBtn").textContent = next.level === 3 ? "Show the solution" : "Give me a bigger hint";
  });
  $("checkBtn").addEventListener("click", async () => {
    if (state.cp === null) return;
    try {
      const r = await api("/api/check", { code: code.value, lesson: state.lesson.id, checkpoint: state.cp });
      const head = r.passed
        ? '<p class="ok">Passed. Your function gave the expected answers.</p><button id="resumeVideo" class="btn primary" type="button">Continue the video</button>'
        : `<p class="bad">Not yet.</p><p>Expected:</p><pre>${esc(r.expected)}</pre><p>Your code printed:</p><pre>${esc(r.got || "(nothing)")}</pre>`;
      if (r.passed) state.passedCp[state.cp] = true;
      out.querySelectorAll(".result").forEach((n) => n.remove());
      out.insertAdjacentHTML("afterbegin", `<div class="result">${head}${r.stderr ? `<pre class="err">${esc(r.stderr)}</pre>` : ""}${explainHtml(r.explain)}</div>`);
    } catch (e) { showError(e); }
  });

  /* ---------- engine and performance drawer ---------- */
  async function refreshHardware() {
    try { state.hw = await api("/api/hardware"); } catch (e) { return; }
    const hw = state.hw, last = hw.last_ocr;
    const npu = last ? last.engine === "npu" : hw.npu_provider_available;
    $("perfChip").innerHTML = `<span class="dot ${npu ? "npu" : ""}"></span>` +
      (last ? `Last frame: ${(last.ms / 1000).toFixed(1)} s on ${last.engine === "npu" ? "NPU" : "CPU"}`
            : hw.npu_provider_available ? "NPU available" : "Running on CPU");
    if (!$("perf").hidden) renderPerf();
  }
  function benchTable(b) {
    if (!b) return "";
    const c = b.results.cpu, n = b.results.npu;
    const cell = (r, k) => (r && r.available ? `${r[k]} ms` : "n/a");
    const rows = [["Average", "mean_ms"], ["Median", "median_ms"], ["Fastest", "min_ms"], ["Slow end (95th)", "p95_ms"], ["Engine start-up", "load_ms"]];
    const why = n && !n.available ? `<div class="note-box">NPU not measured: ${esc(n.reason)}</div>` : "";
    const batt = b.battery_before != null ? `<p class="small">Battery: ${b.battery_before}% before, ${b.battery_after}% after (too small to compare on its own).</p>`
      : '<p class="small muted">This device does not report a battery level to the app.</p>';
    return `<table><tr><th>Same task</th><th>CPU</th><th>NPU</th></tr>` +
      rows.map(([lab, k]) => `<tr><td>${lab}</td><td>${cell(c, k)}</td><td>${cell(n, k)}</td></tr>`).join("") + "</table>" + why + batt +
      `<p class="small muted">${esc(b.task)}. Measured ${esc(new Date(b.at).toLocaleString())}, ${c ? c.runs : 0} runs after one warm-up.</p>`;
  }
  function renderPerf() {
    const hw = state.hw;
    if (!hw) { $("perfBody").innerHTML = '<p class="muted">Reading this laptop…</p>'; return; }
    $("perfBody").innerHTML =
      `<dl><dt>Device</dt><dd>${esc(hw.platform)}</dd><dt>Processor</dt><dd>${esc(hw.machine)}, ${hw.cpu_count} cores</dd>` +
      `<dt>ONNX Runtime</dt><dd>${esc(hw.onnxruntime)}</dd><dt>Accelerators</dt><dd>${esc(hw.providers.join(", "))}</dd>` +
      `<dt>Snapdragon NPU</dt><dd>${hw.npu_provider_available ? "QNN provider found" : "QNN provider not found, using CPU"}</dd>` +
      `<dt>Memory in use</dt><dd>${hw.memory_mb != null ? hw.memory_mb + " MB" : "n/a"}</dd></dl>` +
      `<p><label>Reading engine <select id="engineSel"><option value="auto">Automatic</option><option value="cpu">CPU</option><option value="npu">NPU</option></select></label></p>` +
      `<p><label class="check" style="margin:0"><input type="checkbox" id="lowChk"> Low-resource mode (smaller frames, for older laptops)</label></p>` +
      '<p><button id="benchBtn" class="btn primary" type="button">Run the CPU vs NPU test</button></p><div id="benchOut"></div>' +
      '<div class="note-box">Every number here is measured on this laptop just now. Power draw is not measured by this app. To record it, follow docs/BENCHMARKING.md.</div>';
    $("engineSel").value = state.engine;
    $("lowChk").checked = state.low;
    $("engineSel").addEventListener("change", (e) => { state.engine = e.target.value; save("cs.engine", state.engine); });
    $("lowChk").addEventListener("change", (e) => { state.low = e.target.checked; save("cs.low", state.low); });
    $("benchBtn").addEventListener("click", runBenchmark);
    $("benchOut").innerHTML = benchTable(hw.last_benchmark);
  }
  async function runBenchmark() {
    $("benchBtn").disabled = true;
    $("benchOut").innerHTML = '<p class="muted">Timing the same frame several times. This takes a little while…</p>';
    try {
      const b = await api("/api/benchmark", { lesson: state.lesson.id, runs: 8 });
      $("benchOut").innerHTML = benchTable(b);
    } catch (e) { $("benchOut").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
    $("benchBtn").disabled = false;
  }
  $("perfChip").addEventListener("click", async () => { $("perf").hidden = false; renderPerf(); await refreshHardware(); });
  $("perfClose").addEventListener("click", () => { $("perf").hidden = true; });

  /* ---------- start ---------- */
  video.addEventListener("timeupdate", onTime);
  video.addEventListener("loadedmetadata", () => { onTime(); drawCrop(); });
  video.addEventListener("ended", () => {
    (state.lesson.checkpoints || []).forEach((cp, i) => { if (!state.shownCp[i]) showCheckpoint(i); });
  });

  async function start() {
    try {
      const list = await api("/api/lessons");
      if (!list.length) { $("lessonTitle").textContent = "No lessons found in the lessons folder"; return; }
      const wanted = new URLSearchParams(location.search).get("lesson");
      const id = list.find((l) => l.id === wanted) ? wanted : list[0].id;
      state.lesson = await api("/api/lessons/" + id);
      $("lessonTitle").textContent = state.lesson.title;
      document.title = state.lesson.title + " - CodeSync AI";
      video.src = `/lessons/${id}/${state.lesson.video}`;
      renderTranscript();
      showSlide(0);
      renderNotes();
      renderEditor();
      code.placeholder = "Your code goes here.\nCapture the teacher's code from the video, or type your own.";
    } catch (e) { $("lessonTitle").textContent = "Could not load the lesson: " + e.message; }
    refreshHardware();
  }
  start();
})();
