/* SaaS Rebuild — static web workspace.
 *
 * No backend: the user's Anthropic API key lives in localStorage and requests
 * go straight from the browser to api.anthropic.com using the CORS opt-in
 * header (anthropic-dangerous-direct-browser-access). That header exists for
 * exactly this bring-your-own-key pattern: the key is the user's own and is
 * never proxied through or stored on any server of ours.
 */

"use strict";

// Data base: config.js sets window.SR_DATA_BASE. Local/static hosting serves
// ./data/; a standalone deployment may point this at a raw.githubusercontent
// URL pinned to a commit SHA instead of shipping the data files.
const DATA_BASE = (typeof window !== "undefined" && window.SR_DATA_BASE) || "data/";
const dataUrl = (p) => DATA_BASE + p;

const API_URL = "https://api.anthropic.com/v1/messages";
const API_VERSION = "2023-06-01";
const MAX_TOKENS = 32000;
const STORE = {
  key: "sr.apiKey",
  session: "sr.session.v1",
  settings: "sr.settings.v1",
};

/* ------------------------------------------------ state */

const state = {
  messages: [],          // [{role: "user"|"assistant", content: string}]
  streaming: false,
  abort: null,
  skill: null,           // teardown SKILL.md text
  exportCompliance: null,
  references: {},        // name -> text
  recipeIndex: [],
};

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------ routing */

const VIEWS = ["landing", "workspace", "corpus"];

function route() {
  const hash = location.hash.replace(/^#\//, "");
  const view = hash.startsWith("workspace") ? "workspace"
    : hash.startsWith("corpus") ? "corpus" : "landing";
  for (const v of VIEWS) $("view-" + v).classList.toggle("hidden", v !== view);
  document.querySelectorAll("header.site nav a[data-view]").forEach((a) => {
    a.classList.toggle("active", a.dataset.view === view);
  });
  if (view === "corpus") renderCorpus();
  if (view === "workspace" && !localStorage.getItem(STORE.key)) showKeyModal();
}
window.addEventListener("hashchange", route);

/* ------------------------------------------------ api key */

function showKeyModal() { $("key-modal").classList.remove("hidden"); $("key-input").focus(); }
function hideKeyModal() { $("key-modal").classList.add("hidden"); }

function refreshKeyState() {
  const has = !!localStorage.getItem(STORE.key);
  const el = $("key-state");
  el.textContent = has ? "api key set" : "no api key";
  el.classList.toggle("set", has);
}

$("key-state").addEventListener("click", showKeyModal);
$("key-save").addEventListener("click", () => {
  const v = $("key-input").value.trim();
  if (v) localStorage.setItem(STORE.key, v);
  $("key-input").value = "";
  refreshKeyState();
  hideKeyModal();
});
$("key-clear").addEventListener("click", () => {
  localStorage.removeItem(STORE.key);
  refreshKeyState();
  hideKeyModal();
});
$("key-modal").addEventListener("click", (e) => {
  if (e.target === $("key-modal")) hideKeyModal();
});

/* ------------------------------------------------ data loading */

async function fetchText(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`fetch ${path}: ${r.status}`);
  return r.text();
}

async function loadData() {
  const [skill, xc, refExtraction, refMining, refGraph, idx] = await Promise.all([
    fetchText(dataUrl("skill.md")),
    fetchText(dataUrl("export-compliance.md")),
    fetchText(dataUrl("references/extraction-playbook.md")),
    fetchText(dataUrl("references/process-mining.md")),
    fetchText(dataUrl("references/dependency-graph.md")),
    fetch(dataUrl("recipes/index.json")).then((r) => r.json()),
  ]);
  state.skill = skill;
  state.exportCompliance = xc;
  state.references = {
    extraction: refExtraction,
    mining: refMining,
    graph: refGraph,
  };
  state.recipeIndex = idx;
  const sel = $("recipe-select");
  for (const r of idx) {
    const o = document.createElement("option");
    o.value = r.app;
    o.textContent = `${r.app_name} (${r.category})`;
    sel.appendChild(o);
  }
}

/* ------------------------------------------------ system prompt */

const WEB_PREAMBLE = `You are running the protocol below inside a browser-based chat workspace, not a full agent harness. Adapt it to this environment:

- There is no filesystem, no shell, and no browser-automation connector. The live-tenant "browser walk" is replaced by the user navigating their own tenant and pasting or describing what they see; the document-based methodology applies whenever the user supplies engagement documents, exports, or log samples as pasted text. Label the methodology honestly.
- Never ask the user for credentials, API keys, or tokens, and never ask them to paste secrets into this chat. Guide them to run exports and queries themselves and paste the (sanitized) results.
- Every artifact the protocol writes to disk is instead emitted in the chat as a fenced code block whose info string names the file, e.g. \`\`\`json title=teardown.json ... \`\`\` or \`\`\`markdown title=usage-analysis.md ... \`\`\`. The workspace turns these into downloadable files. Keep artifacts schema-faithful to the templates the protocol names; re-emit the full updated artifact (not a diff) when state changes so downloads are always complete.
- Resumability: the user may paste a previously downloaded teardown.json (or import a saved session). Treat a pasted teardown.json as authoritative state and continue from its recorded phase.
- Where the protocol says AskUserQuestion, ask the questions directly in chat, batched.
- Interview mode: generate interview-questions.md as an artifact for the user to circulate; accept answers pasted back later.
- Validation tooling (validate_artifacts.py) is not runnable here; instead, self-check each artifact against its schema requirements before emitting it, and remind the user they can run the validator from the GitHub repository locally.
- Stay strictly inside the protocol's guardrails: authorized tenants only, extraction-legality checklist before bulk extraction, data-boundary approval before acquisition, preservation is never gated on verdicts.

The protocol follows.

---

`;

function buildSystemPrompt() {
  const mode = $("mode").value;
  if (mode === "export-compliance") {
    return WEB_PREAMBLE + state.exportCompliance;
  }
  let sys = WEB_PREAMBLE + state.skill;
  const refs = [
    ["ref-extraction", "extraction", "references/extraction-playbook.md"],
    ["ref-mining", "mining", "references/process-mining.md"],
    ["ref-graph", "graph", "references/dependency-graph.md"],
  ];
  for (const [box, key, name] of refs) {
    if ($(box).checked) {
      sys += `\n\n---\n\nReference document ${name} (loaded):\n\n` + state.references[key];
    }
  }
  return sys;
}

/* ------------------------------------------------ chat */

function setStatus(text) { $("status").textContent = text; }

function note(text, isError) {
  const div = document.createElement("div");
  div.className = "sysnote" + (isError ? " error" : "");
  div.textContent = text;
  $("chat-scroll").appendChild(div);
  scrollChat();
}

function scrollChat() {
  const sc = $("chat-scroll");
  sc.scrollTop = sc.scrollHeight;
}

function addMessage(role, content) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "you" : "claude";
  const body = document.createElement("div");
  body.className = "body";
  if (role === "user") body.textContent = content;
  else body.innerHTML = renderMarkdown(content);
  wrap.appendChild(who);
  wrap.appendChild(body);
  $("chat-scroll").appendChild(wrap);
  scrollChat();
  return body;
}

async function send() {
  const input = $("input");
  const text = input.value.trim();
  if (!text || state.streaming) return;
  const key = localStorage.getItem(STORE.key);
  if (!key) { showKeyModal(); return; }

  input.value = "";
  state.messages.push({ role: "user", content: text });
  addMessage("user", text);
  persistSession();
  await streamAssistant(key);
}

async function streamAssistant(key) {
  state.streaming = true;
  $("send").disabled = true;
  $("stop").classList.remove("hidden");
  setStatus("thinking…");

  const body = {
    model: $("model").value,
    max_tokens: MAX_TOKENS,
    stream: true,
    system: [
      {
        type: "text",
        text: buildSystemPrompt(),
        cache_control: { type: "ephemeral" },
      },
    ],
    messages: state.messages.map((m) => ({ role: m.role, content: m.content })),
  };

  const bodyEl = addMessage("assistant", "");
  let acc = "";
  let stopReason = null;
  const ctrl = new AbortController();
  state.abort = ctrl;

  try {
    const resp = await fetch(API_URL, {
      method: "POST",
      signal: ctrl.signal,
      headers: {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": API_VERSION,
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      let msg = `API error ${resp.status}`;
      try {
        const err = await resp.json();
        if (err && err.error && err.error.message) msg += `: ${err.error.message}`;
      } catch (_) { /* non-JSON error body */ }
      if (resp.status === 401) msg += " — check your API key (top-right).";
      if (resp.status === 429) msg += " — rate limited; wait and retry.";
      throw new Error(msg);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let lastRender = 0;

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let ev;
        try { ev = JSON.parse(line.slice(6)); } catch (_) { continue; }
        if (ev.type === "content_block_delta" && ev.delta && ev.delta.type === "text_delta") {
          acc += ev.delta.text;
          const now = Date.now();
          if (now - lastRender > 120) {           // throttle DOM updates
            bodyEl.innerHTML = renderMarkdown(acc);
            scrollChat();
            lastRender = now;
          }
        } else if (ev.type === "message_delta" && ev.delta && ev.delta.stop_reason) {
          stopReason = ev.delta.stop_reason;
        } else if (ev.type === "error") {
          throw new Error(ev.error && ev.error.message ? ev.error.message : "stream error");
        }
      }
    }

    bodyEl.innerHTML = renderMarkdown(acc);
    if (stopReason === "refusal") {
      note("The model declined this request for safety reasons (stop_reason: refusal). Rephrase, or confirm the work is on a tenant you administer.", true);
    } else if (stopReason === "max_tokens") {
      note("Response hit the output-token cap — say “continue” to resume.", false);
    }
    setStatus("ready");
  } catch (err) {
    if (err.name === "AbortError") {
      setStatus("stopped");
      note("Generation stopped.", false);
    } else {
      setStatus("error");
      note(String(err.message || err), true);
    }
  } finally {
    if (acc) state.messages.push({ role: "assistant", content: acc });
    else bodyEl.parentElement.remove();
    persistSession();
    state.streaming = false;
    state.abort = null;
    $("send").disabled = false;
    $("stop").classList.add("hidden");
    scrollChat();
  }
}

$("send").addEventListener("click", send);
$("stop").addEventListener("click", () => { if (state.abort) state.abort.abort(); });
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});

/* ------------------------------------------------ recipe attach */

$("attach-recipe").addEventListener("click", async () => {
  const slug = $("recipe-select").value;
  if (!slug) return;
  try {
    const text = await fetchText(dataUrl(`recipes/${slug}.json`));
    const meta = state.recipeIndex.find((r) => r.app === slug);
    const msg =
      `Attaching the extraction recipe for ${meta ? meta.app_name : slug} from the corpus. ` +
      `Treat it as a document-derived route hypothesis: re-verify freshness, entitlements, and every route against my tenant before use.\n\n` +
      "```json title=" + slug + ".recipe.json\n" + text.trim() + "\n```";
    state.messages.push({ role: "user", content: msg });
    addMessage("user", `[attached extraction recipe: ${slug}]`);
    persistSession();
    note(`Recipe ${slug} attached. It will be included with your next message's context.`, false);
  } catch (e) {
    note(`Could not load recipe ${slug}: ${e.message}`, true);
  }
});

/* ------------------------------------------------ session persistence */

function persistSession() {
  try {
    localStorage.setItem(STORE.session, JSON.stringify({ v: 1, messages: state.messages }));
    localStorage.setItem(STORE.settings, JSON.stringify({
      mode: $("mode").value,
      model: $("model").value,
      refs: ["ref-extraction", "ref-mining", "ref-graph"].map((id) => $(id).checked),
    }));
  } catch (_) { /* storage full — session export still works */ }
}

function restoreSession() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE.settings) || "null");
    if (s) {
      $("mode").value = s.mode || "teardown";
      $("model").value = s.model || "claude-opus-5";
      ["ref-extraction", "ref-mining", "ref-graph"].forEach((id, i) => {
        $(id).checked = !!(s.refs && s.refs[i]);
      });
    }
    const sess = JSON.parse(localStorage.getItem(STORE.session) || "null");
    if (sess && Array.isArray(sess.messages) && sess.messages.length) {
      state.messages = sess.messages;
      for (const m of state.messages) addMessage(m.role, m.content);
      note("Restored previous session from this browser.", false);
    }
  } catch (_) { /* corrupt storage — start fresh */ }
}

function download(name, text, type) {
  const blob = new Blob([text], { type: type || "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

$("export-session").addEventListener("click", () => {
  download("saas-rebuild-session.json",
    JSON.stringify({ v: 1, exported_at: new Date().toISOString(), messages: state.messages }, null, 2),
    "application/json");
});

$("import-session").addEventListener("click", () => $("import-file").click());
$("import-file").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  try {
    const data = JSON.parse(await f.text());
    if (!Array.isArray(data.messages)) throw new Error("no messages array");
    state.messages = data.messages;
    $("chat-scroll").querySelectorAll(".msg, .sysnote").forEach((n) => {
      if (n.id !== "welcome-note") n.remove();
    });
    for (const m of state.messages) addMessage(m.role, m.content);
    persistSession();
    note("Session imported.", false);
  } catch (err) {
    note("Could not import session: " + err.message, true);
  }
  e.target.value = "";
});

$("export-transcript").addEventListener("click", () => {
  const md = state.messages
    .map((m) => `## ${m.role === "user" ? "You" : "Claude"}\n\n${m.content}`)
    .join("\n\n---\n\n");
  download("saas-rebuild-transcript.md", md, "text/markdown");
});

$("clear-session").addEventListener("click", () => {
  if (!confirm("Clear the conversation? Export first if you want to keep it.")) return;
  state.messages = [];
  localStorage.removeItem(STORE.session);
  $("chat-scroll").querySelectorAll(".msg, .sysnote").forEach((n) => {
    if (n.id !== "welcome-note") n.remove();
  });
  setStatus("ready");
});

/* ------------------------------------------------ markdown rendering */

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderInline(s) {
  let out = escapeHtml(s);
  out = out.replace(/`([^`]+)`/g, (_, c) => "<code>" + c + "</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  out = out.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return out;
}

// Fence info strings like:  json title=teardown.json   |  json  |  markdown title=REBUILD_PLAN.md
function parseFenceInfo(info) {
  const m = info.trim().match(/^([\w+-]*)\s*(?:title=)?(\S+\.[A-Za-z0-9]{1,8})?/);
  return { lang: (m && m[1]) || "", filename: (m && m[2]) || null };
}

let blockCounter = 0;

function renderMarkdown(src) {
  const lines = src.split("\n");
  const out = [];
  let i = 0;

  const flushPara = (buf) => {
    if (buf.length) { out.push("<p>" + renderInline(buf.join(" ")) + "</p>"); buf.length = 0; }
  };

  const para = [];
  while (i < lines.length) {
    const line = lines[i];

    // fenced code
    const fence = line.match(/^```(.*)$/);
    if (fence) {
      flushPara(para);
      const { lang, filename } = parseFenceInfo(fence[1]);
      const code = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) { code.push(lines[i]); i++; }
      i++; // closing fence (or EOF while streaming)
      const codeText = code.join("\n");
      const id = "cb" + (++blockCounter);
      const label = filename ? `<span class="fname">${escapeHtml(filename)}</span>` :
        `<span>${escapeHtml(lang || "text")}</span>`;
      out.push(
        `<div class="codeblock"><div class="bar">${label}<span class="spacer"></span>` +
        `<button data-copy="${id}">copy</button>` +
        `<button data-download="${id}" data-fname="${escapeHtml(filename || (lang ? "snippet." + lang : "snippet.txt"))}">download</button>` +
        `</div><pre id="${id}">${escapeHtml(codeText)}</pre></div>`);
      continue;
    }

    // table
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length &&
        /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      flushPara(para);
      const splitRow = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const header = splitRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(splitRow(lines[i])); i++; }
      let t = "<div class=\"tbl-wrap\"><table><thead><tr>";
      t += header.map((h) => "<th>" + renderInline(h) + "</th>").join("");
      t += "</tr></thead><tbody>";
      for (const r of rows) t += "<tr>" + r.map((c) => "<td>" + renderInline(c) + "</td>").join("") + "</tr>";
      t += "</tbody></table></div>";
      out.push(t);
      continue;
    }

    // heading
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { flushPara(para); out.push(`<h${h[1].length}>${renderInline(h[2])}</h${h[1].length}>`); i++; continue; }

    // hr
    if (/^\s*---+\s*$/.test(line)) { flushPara(para); out.push("<hr>"); i++; continue; }

    // blockquote
    if (/^\s*>\s?/.test(line)) {
      flushPara(para);
      const q = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) { q.push(lines[i].replace(/^\s*>\s?/, "")); i++; }
      out.push("<blockquote>" + renderMarkdown(q.join("\n")) + "</blockquote>");
      continue;
    }

    // lists
    const ul = line.match(/^\s*[-*]\s+(.*)$/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (ul || ol) {
      flushPara(para);
      const tag = ul ? "ul" : "ol";
      const items = [];
      const re = ul ? /^\s*[-*]\s+(.*)$/ : /^\s*\d+[.)]\s+(.*)$/;
      while (i < lines.length) {
        const m = lines[i].match(re);
        if (m) { items.push(m[1]); i++; }
        else if (/^\s{2,}\S/.test(lines[i]) && items.length) {
          items[items.length - 1] += " " + lines[i].trim(); i++;
        } else break;
      }
      out.push(`<${tag}>` + items.map((it) => "<li>" + renderInline(it) + "</li>").join("") + `</${tag}>`);
      continue;
    }

    // blank
    if (/^\s*$/.test(line)) { flushPara(para); i++; continue; }

    para.push(line.trim());
    i++;
  }
  flushPara(para);
  return out.join("\n");
}

// code block copy/download (event delegation)
document.addEventListener("click", (e) => {
  const copyId = e.target.dataset && e.target.dataset.copy;
  const dlId = e.target.dataset && e.target.dataset.download;
  if (copyId) {
    const pre = document.getElementById(copyId);
    if (pre) navigator.clipboard.writeText(pre.textContent).then(() => {
      e.target.textContent = "copied";
      setTimeout(() => { e.target.textContent = "copy"; }, 1200);
    });
  } else if (dlId) {
    const pre = document.getElementById(dlId);
    if (pre) download(e.target.dataset.fname || "artifact.txt", pre.textContent);
  } else if (e.target.dataset && e.target.dataset.recipeDl) {
    const slug = e.target.dataset.recipeDl;
    fetchText(dataUrl(`recipes/${slug}.json`))
      .then((t) => download(`${slug}.recipe.json`, t, "application/json"))
      .catch(() => {});
  }
});

/* ------------------------------------------------ corpus view */

let corpusRendered = false;

function renderCorpus() {
  if (corpusRendered || !state.recipeIndex.length) return;
  corpusRendered = true;
  drawRecipeGrid("");
  $("recipe-filter").addEventListener("input", (e) => drawRecipeGrid(e.target.value));
}

function drawRecipeGrid(filter) {
  const grid = $("recipe-grid");
  grid.innerHTML = "";
  const f = filter.trim().toLowerCase();
  for (const r of state.recipeIndex) {
    const hay = `${r.app_name} ${r.vendor} ${r.category}`.toLowerCase();
    if (f && !hay.includes(f)) continue;
    const card = document.createElement("div");
    card.className = "recipe-card";
    card.innerHTML =
      `<div class="name">${escapeHtml(r.app_name)}</div>` +
      `<div class="meta">${escapeHtml(r.vendor)} · ${escapeHtml(r.category)} · ${r.routes} route${r.routes === 1 ? "" : "s"}</div>`;
    card.addEventListener("click", () => showRecipe(r.app));
    grid.appendChild(card);
  }
}

async function showRecipe(slug) {
  const el = $("recipe-detail");
  el.classList.remove("hidden");
  el.innerHTML = "<p class=\"mono\">loading…</p>";
  try {
    const recipe = JSON.parse(await fetchText(dataUrl(`recipes/${slug}.json`)));
    let html = `<h2>${escapeHtml(recipe.app_name || slug)}</h2>` +
      `<div class="meta">${escapeHtml(recipe.vendor || "")} · ${escapeHtml(recipe.category || "")} · schema ${escapeHtml(recipe.schema_version || "")}</div>`;
    if (recipe.export_rights && recipe.export_rights.summary) {
      html += `<h3>Export rights</h3><p style="font-size:0.9rem">${escapeHtml(recipe.export_rights.summary)}</p>`;
      if (recipe.export_rights.tos_url) {
        html += `<p class="mono" style="font-size:0.75rem"><a href="${escapeHtml(recipe.export_rights.tos_url)}" target="_blank" rel="noopener">${escapeHtml(recipe.export_rights.tos_url)}</a></p>`;
      }
    }
    if (Array.isArray(recipe.routes)) {
      html += `<h3>Routes (${recipe.routes.length})</h3>`;
      for (const rt of recipe.routes) {
        html += `<div class="route"><span class="rt">${escapeHtml(rt.route_type || "route")}</span> — ` +
          `${escapeHtml(rt.how || "")}` +
          (Array.isArray(rt.covers) ? `<div class="covers">covers: ${escapeHtml(rt.covers.join(", "))}</div>` : "") +
          `</div>`;
      }
    }
    html += `<p style="margin-top:1rem"><button class="btn secondary" data-recipe-dl="${escapeHtml(slug)}">Download recipe JSON</button></p>`;
    el.innerHTML = html;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    el.innerHTML = `<p>Could not load recipe: ${escapeHtml(e.message)}</p>`;
  }
}

/* ------------------------------------------------ settings change hooks */

["mode", "model"].forEach((id) => $(id).addEventListener("change", persistSession));
["ref-extraction", "ref-mining", "ref-graph"].forEach((id) =>
  $(id).addEventListener("change", persistSession));

/* ------------------------------------------------ boot */

(async function boot() {
  refreshKeyState();
  route();
  try {
    await loadData();
    // Re-run the router now that data is loaded: a direct load or refresh of
    // #/corpus routed before recipeIndex existed, so renderCorpus() bailed.
    route();
    restoreSession();
  } catch (e) {
    note("Failed to load protocol data: " + e.message, true);
  }
})();
