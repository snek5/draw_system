// Runs the ORIGINAL React-era helpers.js (reference/helpers.js; logic
// unmodified, only names renamed to match the VIP_FLAG column)
// with the browser APIs it touches stubbed, and prints what it produced.
//
// stdin:  JSON {"cases": [...]} - see tests/test_parity.py
// stdout: JSON {"results": [...]}
//
// Also exposes raw seedrandom() and V8 sort probes so the Python building
// blocks can be checked on their own.

import seedrandom from "seedrandom";
import cryptoJs from "crypto-js";

let alerts = [];
let timers = [];
let blobText = null;

globalThis.alert = (msg) => alerts.push(String(msg));
globalThis.setTimeout = (fn, delay) => timers.push({ fn, delay: Number.isNaN(delay) ? 0 : delay, seq: timers.length });
globalThis.FileReader = class {
  readAsText(file) { this.onload({ target: { result: file.text } }); }
  readAsArrayBuffer(file) { this.result = file.buffer; this.onload(); }
};
globalThis.Blob = class { constructor(parts) { this.text = parts.join(""); } };
globalThis.URL.createObjectURL = (blob) => { blobText = blob.text; return "blob:x"; };
globalThis.document = {
  createElement: () => ({ click() {} }),
  body: { appendChild() {}, removeChild() {} },
};

const { pickWinners, pickStaff, downloadSelectedLines, hashFile } =
  await import("./reference/helpers.js");

// Event loop for the captured timers: by delay, then insertion order.
// An exception in one callback doesn't stop the others (as in a browser).
function flushTimers() {
  const errors = [];
  const ordered = [...timers].sort((a, b) => a.delay - b.delay || a.seq - b.seq);
  timers = [];
  for (const t of ordered) {
    try { t.fn(); } catch (e) { errors.push(String(e)); }
  }
  return errors;
}

function runDraw(c) {
  alerts = [];
  timers = [];
  let display = [];
  let picked = [];
  let headers = null;
  let error = null;
  const args = {
    fileInput: { text: c.content },
    lineDelay: c.delay ?? 0,
    setRandomLine: (f) => { display = f(display); },
    setPickedLines: (f) => { picked = f(picked); },
    setFileHeaders: (h) => { headers = h; },
    rngSeed: c.seed,
    showName: c.showName,
    showCertificate: c.showCert,
  };
  try {
    if (c.mode === "staff") pickStaff({ ...args, staffWinners: parseInt(c.staff) });
    else pickWinners({ ...args, vipWinners: parseInt(c.vip), nonVipWinners: parseInt(c.mass) });
  } catch (e) {
    error = String(e);
  }
  const timerErrors = flushTimers();
  let download = null;
  if (headers) {
    blobText = null;
    downloadSelectedLines(headers, picked, c.seed, c.hash ?? "HASH");
    download = blobText;
  }
  return { alerts, error, display, picked, headers, timerErrors, download };
}

function runHash(c) {
  let hashed = null, seed = null;
  const bytes = Buffer.from(c.base64, "base64");
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  hashFile({ buffer }, (h) => { hashed = h; }, (s) => { seed = s; });
  return { hashed, seed };
}

function runRng(c) {
  const rng = seedrandom(c.seed);
  return { values: Array.from({ length: c.n }, () => rng()) };
}

function runSort(c) {
  const rng = seedrandom(c.seed);
  const arr = Array.from({ length: c.n }, (_, i) => i);
  let calls = 0;
  arr.sort(() => { calls++; return rng() - 0.5; });
  return { order: arr, calls, next: rng() };
}

const input = JSON.parse(await new Promise((resolve) => {
  let buf = "";
  process.stdin.on("data", (d) => (buf += d));
  process.stdin.on("end", () => resolve(buf));
}));

const console_log = console.log;
console.log = () => {}; // helpers.js logs seeds/hashes; keep stdout clean

const results = input.cases.map((c) => {
  switch (c.kind) {
    case "draw": return runDraw(c);
    case "hash": return runHash(c);
    case "rng": return runRng(c);
    case "sort": return runSort(c);
    default: throw new Error(`unknown case kind ${c.kind}`);
  }
});

console_log(JSON.stringify({ results }));
