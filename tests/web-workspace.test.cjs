const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const web = path.resolve(__dirname, "../web");
const app = fs.readFileSync(path.join(web, "app.js"), "utf8");

function workspace() {
  const nodes = new Map();
  const values = new Map();
  const handlers = new Map();
  function node() {
    return {
      textContent: "", innerHTML: "", value: "", dataset: {},
      classList: { add() {}, remove() {}, toggle() {} },
      addEventListener(type, handler) { this[type] = handler; },
      querySelectorAll() { return []; },
      appendChild() {},
      click() {},
      remove() {},
    };
  }
  function getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, node());
    return nodes.get(id);
  }
  const context = vm.createContext({
    AbortController, TextDecoder, Blob, URL, setTimeout() {},
    window: { addEventListener() {} },
    location: { hash: "#/netsuite" },
    document: {
      getElementById, createElement: node, querySelectorAll: () => [],
      addEventListener(type, handler) { handlers.set(type, handler); },
    },
    localStorage: {
      getItem: (key) => values.get(key),
      setItem: (key, value) => values.set(key, value),
    },
  });
  // Exercise the handlers with mock browser primitives and no live API.
  vm.runInContext(app.slice(0, app.indexOf("(async function boot()")), context);
  return { context, getElementById, handlers, values };
}

test("NetSuite preview and copied prompt load without an API key", async () => {
  const { context, getElementById } = workspace();
  context.fetch = async (url) => ({
    ok: true,
    text: async () => fs.readFileSync(path.join(web, url), "utf8"),
  });
  let copied = "";
  context.navigator = { clipboard: { writeText: async (value) => { copied = value; } } };
  context.route();
  await getElementById("copy-netsuite-prompt").click();
  assert.match(getElementById("netsuite-example").innerHTML, /480 distinct headers/);
  assert.match(copied, /Confirm scope before reading the tenant/);
});

for (const reason of [null, "max_tokens", "end_turn"]) {
  test(`artifact download eligibility with stream stop reason ${reason}`, async () => {
    const { context, values } = workspace();
    const events = [
      { type: "content_block_delta", delta: { type: "text_delta", text: '```json title=teardown.json\n{}\n```' } },
    ];
    if (reason) {
      events.push({ type: "message_delta", delta: { stop_reason: reason } }, { type: "message_stop" });
    }
    const bytes = new TextEncoder().encode(events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""));
    context.fetch = async () => ({
      ok: true,
      body: { getReader: () => {
        let sent = false;
        return { read: async () => {
          if (sent) return { done: true };
          sent = true;
          return { value: bytes };
        } };
      } },
    });
    await context.streamAssistant("mock-key");
    const { messages: [message] } = JSON.parse(values.get("sr.session.v1"));
    assert.equal(message.complete, reason === "end_turn");
    const restored = context.renderAssistant(message.content, message.complete);
    assert.equal(restored.includes("data-download="), reason === "end_turn");
  });
}

test("artifact handler refuses malformed JSON before download", () => {
  const { context, getElementById, handlers } = workspace();
  const downloads = [];
  context.download = (...args) => downloads.push(args);
  const block = getElementById("cb1");
  const click = handlers.get("click");
  const event = { target: { dataset: { download: "cb1", fname: "teardown.json" } } };
  block.textContent = '{"unfinished":';
  click(event);
  assert.equal(downloads.length, 0);
  block.textContent = '{"complete":true}';
  click(event);
  assert.deepEqual(downloads, [["teardown.json", '{"complete":true}']]);
});
