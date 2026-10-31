# Aspirasi 6 Draw System

A draw system for the "Aspirasi 6" campaign managed by BIBD Bank, used to select winners from a participant file according to set criteria. It is built with Flask and htmx; it was previously a Vite + React single-page app.

Given the same participant file and RNG seed, it picks **the same winners, in the same order, as the React version did**, so earlier draws can still be reproduced and audited (see [Draw compatibility](#draw-compatibility)).

## Features

- **Upload CSV**: upload the pipe-delimited (`|`) participant file.
- **Hash value**: the file's SHA-256 hash is shown on upload and recorded in the results.
- **RNG seed**: a random seed is generated on upload; it can be replaced before the draw.
- **Staff toggle**: switch between the public draw and the staff draw.
- **Public draw parameters**: number of Perdana winners, number of Mass Market winners, delay between lines.
- **Staff draw parameters**: number of staff winners, delay between lines.
- **Display options**: show certificate (`ACCTNO`), name (`ACNAME`), or both.
- **Draw**: click the logo to run the draw; winners are revealed one at a time.
- **Download**: press **Spacebar** on the draw screen to download `selected_lines.csv` with the winners revealed so far, plus the RNG seed and file hash.

## Running it

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app fallback run
```

Then open http://127.0.0.1:5000.

htmx and all styles are bundled in `fallback/static`, so the app needs no internet connection and no Node build.

Run it as a **single process** on the draw machine; the Flask dev server above is fine for that. The uploaded file is held in memory only and never written to disk, so restarting the server or reloading the page starts a fresh draw.

Optional environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `FALLBACK_SECRET_KEY` | random per start | Session signing key |
| `FALLBACK_MAX_UPLOAD_MB` | `200` | Largest participant file accepted |

## Participant file

The file is pipe-delimited, with a header row. The draw uses these columns:

| Column | Used for |
| --- | --- |
| `PERDANA_FLAG` | `Y` = Perdana, `N` = Mass Market (public draw) |
| `STAFF_FLAG` | `N` = eligible for the public draw, `Y` = eligible for the staff draw |
| `FINAL_CHANCES` | Weight in the public draw (staff draw is equal-chance) |
| `ACNAME` | Name shown when "Show Name" is ticked |
| `ACCTNO` | Certificate shown when "Show Certificate" is ticked |

## Project layout

```
fallback/
  draw.py        the draw (ported from the React app's helpers.js)
  jscompat.py    exact ports of seedrandom, V8's sort and JS string/number rules
  views.py       routes for the htmx UI
  state.py       in-memory per-browser draw state
  templates/     pages and htmx partials
  static/        CSS, images, vendored htmx 2.0.4
tests/
  test_app.py    end-to-end flow through the routes
  test_parity.py the Python draw vs. the original JavaScript, run in Node
  parity/        the original helpers.js (unmodified) and its harness
```

## Tests

```bash
pip install -r requirements-dev.txt
npm install --prefix tests/parity   # only for the parity tests; needs Node
python -m pytest
```

The parity tests run the original `helpers.js` from the React app in Node, with the same `seedrandom` 3.0.5 and `crypto-js` 4.2.0. They compare it with the Python port across about 900 generated files and seeds, checking winners, reveal order, labels and the downloaded file. They also check the RNG output and the shuffle (V8's `Array.prototype.sort`) value by value. Without Node they are skipped.

## Draw compatibility

The old draw ran in the browser: `seedrandom(seed)` (ARC4), a weighted pick, then a shuffle via `array.sort(() => rng() - 0.5)`. To keep old seeds reproducible, `fallback/draw.py` repeats this exactly, including the shuffle's dependence on how Chrome/V8 sorts. Draws made in other browsers (e.g. Firefox) used a different sort and may not reproduce.

The original weighted pick also has quirks that are **kept on purpose** so results match:

- After each winner is removed, the running weights aren't recalculated, so later picks don't use the true remaining weights.
- In the public draw, a random value that lands on an ineligible row (e.g. a Mass Market row during the Perdana picks) goes to the next eligible row after it.
- If no eligible row is left at or after the random value, the draw can't continue. The old app silently showed nothing; this version shows an error. On clean files this is rare but real: roughly 1 in 200 seeds in testing.

Fixing these would change which winners a given seed produces, so it should be a deliberate, separately versioned change.

## Auditable Draw System Guidelines

1. **Data Integrity Verification**
   - Before starting the draw, verify the participant file's format, completeness and correctness.

2. **Randomization Process**
   - Use a secure and unbiased random number generator (RNG) to keep the selection fair.
   - Record the RNG seed used for each draw session for the audit trail.

3. **Draw Execution**
   - Document the draw process, including the selection criteria, parameters and any specific rules applied (e.g. staff vs. public draw).
   - Log all draw actions and outcomes, including the selected winners and relevant details.

4. **Participant Eligibility**
   - Validate the eligibility criteria and make sure only eligible participants are included.
   - Keep clear documentation of the eligibility criteria and how they are applied.

5. **Transparency**
   - Show relevant information during the draw, such as the number of participants, winners selected and any filtering criteria applied.
   - Let stakeholders review the results and verify the integrity of the selection process.

6. **Hash Value and File Integrity**
   - Generate a hash of the uploaded file to confirm its integrity and authenticity.
   - Record the hash and include it in the draw results for verification.

7. **Downloadable Results**
   - Let users download the draw results, including participant details and outcomes, in a structured format (CSV).
   - Include the RNG seed and file hash in the downloaded results for auditability.
