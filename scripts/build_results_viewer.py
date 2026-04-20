#!/usr/bin/env python3
"""Build a self-contained static HTML viewer for eval scenarios + results.

Reads:
  tests/scenarios/*/scenario.json   (scenario definitions)
  results/<model-slug>/<scenario>.json   (one file per model × scenario)

Writes:
  results/index.html   (single-file viewer — open directly in a browser)

Usage:
  python scripts/build_results_viewer.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = ROOT / "tests" / "scenarios"
RESULTS_DIR = ROOT / "results"
OUTPUT = RESULTS_DIR / "index.html"


def load_scenarios() -> dict[str, dict]:
    scenarios: dict[str, dict] = {}
    for scenario_path in sorted(SCENARIOS_DIR.iterdir()):
        spec = scenario_path / "scenario.json"
        if not spec.exists():
            continue
        scenarios[scenario_path.name] = json.loads(spec.read_text())
    return scenarios


def load_results() -> dict[str, dict[str, dict]]:
    """Return {model_slug: {scenario_dir_name: report}}."""
    out: dict[str, dict[str, dict]] = {}
    if not RESULTS_DIR.exists():
        return out
    for model_dir in sorted(RESULTS_DIR.iterdir()):
        if not model_dir.is_dir():
            continue
        reports: dict[str, dict] = {}
        for report_file in sorted(model_dir.glob("*.json")):
            reports[report_file.stem] = json.loads(report_file.read_text())
        if reports:
            out[model_dir.name] = reports
    return out


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Palio Bot — Eval Results</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/diff2html/bundles/css/diff2html.min.css" />
<script src="https://cdn.jsdelivr.net/npm/diff2html/bundles/js/diff2html-ui.min.js"></script>
<style>
  :root {
    --bg: #0f1115;
    --panel: #171a21;
    --panel-2: #1d222b;
    --border: #262c38;
    --text: #e6e8eb;
    --muted: #8a93a6;
    --accent: #7aa2ff;
    --pass: #3ecf8e;
    --fail: #ff6b6b;
    --warn: #f2c94c;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; }
  body {
    background: var(--bg); color: var(--text);
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  code, pre { font-family: ui-monospace, "SF Mono", Menlo, monospace; }
  .app { display: grid; grid-template-columns: 260px 1fr; height: 100vh; }
  aside {
    background: var(--panel); border-right: 1px solid var(--border);
    overflow-y: auto; padding: 16px 12px;
  }
  aside h2 {
    font-size: 11px; letter-spacing: 1px; text-transform: uppercase;
    color: var(--muted); margin: 12px 8px 8px;
  }
  .nav-item {
    display: block; padding: 8px 10px; border-radius: 6px;
    color: var(--text); text-decoration: none; cursor: pointer;
    font-size: 13px; margin-bottom: 2px;
  }
  .nav-item:hover { background: var(--panel-2); }
  .nav-item.active { background: #2a3550; color: var(--accent); }
  .nav-item .sub { color: var(--muted); font-size: 11px; margin-left: 6px; }
  main { overflow-y: auto; padding: 24px 32px; }
  h1 { margin: 0 0 4px; font-size: 22px; }
  .subtitle { color: var(--muted); margin-bottom: 24px; }
  .scenario-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }
  .card {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 8px; padding: 14px; cursor: pointer;
    transition: border-color .15s;
  }
  .card:hover { border-color: var(--accent); }
  .card h3 { margin: 0 0 6px; font-size: 14px; }
  .card .meta { color: var(--muted); font-size: 12px; }
  .pill {
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    font-size: 11px; font-weight: 600;
  }
  .pill.pass { background: rgba(62,207,142,.15); color: var(--pass); }
  .pill.fail { background: rgba(255,107,107,.15); color: var(--fail); }
  .pill.warn { background: rgba(242,201,76,.15); color: var(--warn); }
  .pill.muted { background: var(--panel-2); color: var(--muted); }
  .step {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 8px; margin-bottom: 12px; overflow: hidden;
  }
  .step-head {
    padding: 12px 16px; cursor: pointer;
    display: flex; align-items: center; gap: 10px;
    background: var(--panel);
  }
  .step-head:hover { background: var(--panel-2); }
  .step-head .prompt {
    flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
    color: var(--text);
  }
  .step-head .id { color: var(--muted); font-size: 12px; font-family: ui-monospace, monospace; }
  .step-body { padding: 16px; border-top: 1px solid var(--border); display: none; background: var(--panel-2); }
  .step.open .step-body { display: block; }
  .section { margin-bottom: 14px; }
  .section h4 {
    margin: 0 0 6px; font-size: 11px; letter-spacing: .5px;
    text-transform: uppercase; color: var(--muted);
  }
  pre.text {
    background: #0b0d12; border: 1px solid var(--border);
    border-radius: 6px; padding: 10px; white-space: pre-wrap;
    overflow-x: auto; max-height: 500px; overflow-y: auto;
    margin: 0; font-size: 12.5px;
  }
  .tool-calls { display: flex; flex-wrap: wrap; gap: 6px; }
  .tag {
    background: var(--panel); border: 1px solid var(--border);
    padding: 2px 8px; border-radius: 4px; font-size: 11px;
    font-family: ui-monospace, monospace;
  }
  .judge {
    background: #0b0d12; border: 1px solid var(--border);
    border-radius: 6px; padding: 10px; font-size: 12.5px;
  }
  .judge .crit { margin: 2px 0; color: var(--muted); }
  .crumbs { color: var(--muted); font-size: 12px; margin-bottom: 16px; }
  .crumbs a { color: var(--accent); cursor: pointer; text-decoration: none; }
  .crumbs a:hover { text-decoration: underline; }
  .stat-row { display: flex; gap: 16px; color: var(--muted); font-size: 12px; margin-bottom: 16px; }
  .stat-row b { color: var(--text); }
  .empty { color: var(--muted); text-align: center; padding: 40px; }
  /* diff2html dark tweaks */
  .diff-file { margin-top: 8px; }
  .diff-file-name {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px; color: var(--muted);
    padding: 4px 8px;
    border: 1px solid var(--border); border-bottom: none;
    background: var(--panel);
    border-radius: 6px 6px 0 0;
  }
  .diff-container { position: relative; }
  .diff-container .d2h-file-wrapper { border-radius: 0 0 6px 6px; }
  /* diff2html's line-number column is position: absolute and anchors to the
     nearest positioned ancestor. Without these, it anchors up to <body> and
     "sticks" to the viewport while the code scrolls inside <main>. */
  .diff-container .d2h-wrapper,
  .diff-container .d2h-file-wrapper,
  .diff-container .d2h-files-diff,
  .diff-container .d2h-file-side-diff,
  .diff-container .d2h-code-wrapper,
  .diff-container .d2h-diff-table { position: relative; }
  .diff-container .d2h-file-header { background: var(--panel); border-color: var(--border); }
  .diff-container .d2h-file-name { color: var(--text); }
  .diff-container .d2h-code-line-ctn { white-space: pre-wrap; }
</style>
</head>
<body>
<div class="app">
  <aside>
    <h2>Models</h2>
    <div id="nav-models"></div>
    <h2 style="margin-top: 20px;">Scenarios</h2>
    <div id="nav-scenarios"></div>
  </aside>
  <main id="main"></main>
</div>

<script>
const SCENARIOS = __SCENARIOS__;
const RESULTS = __RESULTS__;

const state = { model: null, scenario: null };
const pendingDiffs = [];  // [{ id, unified }]
let diffCounter = 0;

function queueDiff(diffs) {
  if (!diffs || !Object.keys(diffs).length) return "";
  // One container per file so each gets its own filename label above.
  const blocks = Object.entries(diffs).map(([path, text]) => {
    const id = "diff-" + (++diffCounter);
    // Keep "--- expected" / "+++ actual" so the diff2html header literally reads
    // "expected → actual". Filename is shown separately above.
    pendingDiffs.push({ id, unified: String(text) });
    return `<div class="diff-file">
      <div class="diff-file-name">${escapeHtml(path)}</div>
      <div id="${id}" class="diff-container"></div>
    </div>`;
  }).join("");
  return `<div class="section"><h4>Diffs</h4>${blocks}</div>`;
}

function flushDiffs() {
  if (!window.Diff2HtmlUI) return;
  while (pendingDiffs.length) {
    const { id, unified } = pendingDiffs.shift();
    const target = document.getElementById(id);
    if (!target) continue;
    const ui = new Diff2HtmlUI(target, unified, {
      drawFileList: false,
      matching: "lines",
      outputFormat: "side-by-side",
      colorScheme: "dark",
      renderNothingWhenEmpty: true,
    });
    ui.draw();
  }
}

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function modelTotals(model) {
  const reports = RESULTS[model] || {};
  let passed = 0, total = 0;
  for (const r of Object.values(reports)) {
    passed += r.passed ?? 0;
    total += r.total ?? 0;
  }
  return { passed, total };
}

function renderNav() {
  const modelsEl = document.getElementById("nav-models");
  const scenariosEl = document.getElementById("nav-scenarios");

  const models = Object.keys(RESULTS).sort();
  modelsEl.innerHTML = models.length === 0
    ? '<div class="nav-item" style="color:var(--muted)">no results yet</div>'
    : models.map(m => {
        const t = modelTotals(m);
        const active = state.model === m && !state.scenario ? "active" : "";
        return `<a class="nav-item ${active}" onclick="selectModel('${m}')">
          ${escapeHtml(m)}
          <span class="sub">${t.passed}/${t.total}</span>
        </a>`;
      }).join("");

  const scenarios = Object.keys(SCENARIOS).sort();
  scenariosEl.innerHTML = scenarios.map(s => {
    const active = state.scenario === s && !state.model ? "active" : "";
    return `<a class="nav-item ${active}" onclick="selectScenario('${s}')">${escapeHtml(s)}</a>`;
  }).join("");
}

function selectModel(m) {
  state.model = m;
  state.scenario = null;
  state.step = null;
  renderNav(); renderMain();
}
function selectScenario(s) {
  state.scenario = s;
  state.model = null;
  state.step = null;
  renderNav(); renderMain();
}
function selectPair(model, scenario) {
  state.model = model;
  state.scenario = scenario;
  renderNav(); renderMain();
}
function clearSelection() {
  state.model = null; state.scenario = null;
  renderNav(); renderMain();
}

function renderMain() {
  const el = document.getElementById("main");
  pendingDiffs.length = 0;
  if (state.model && state.scenario) el.innerHTML = renderPair(state.model, state.scenario);
  else if (state.model) el.innerHTML = renderModel(state.model);
  else if (state.scenario) el.innerHTML = renderScenario(state.scenario);
  else el.innerHTML = renderHome();
  flushDiffs();
}

function renderHome() {
  const models = Object.keys(RESULTS).sort();
  const scenarios = Object.keys(SCENARIOS).sort();
  return `
    <h1>Palio Bot — Eval Results</h1>
    <div class="subtitle">${models.length} model(s) · ${scenarios.length} scenario(s)</div>
    <h2 style="font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;">Models</h2>
    <div class="scenario-grid">
      ${models.map(m => {
        const t = modelTotals(m);
        const pct = t.total ? Math.round(100 * t.passed / t.total) : 0;
        const cls = t.passed === t.total ? "pass" : (t.passed === 0 ? "fail" : "warn");
        return `<div class="card" onclick="selectModel('${m}')">
          <h3>${escapeHtml(m)}</h3>
          <div class="meta">
            <span class="pill ${cls}">${t.passed}/${t.total} · ${pct}%</span>
            <span style="margin-left:8px">${Object.keys(RESULTS[m]).length} scenario runs</span>
          </div>
        </div>`;
      }).join("")}
    </div>
    <h2 style="font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;">Scenarios</h2>
    <div class="scenario-grid">
      ${scenarios.map(s => {
        const spec = SCENARIOS[s];
        return `<div class="card" onclick="selectScenario('${s}')">
          <h3>${escapeHtml(s)}</h3>
          <div class="meta">${(spec.steps || []).length} step(s)${spec.reset_between_steps ? " · reset" : ""}</div>
        </div>`;
      }).join("")}
    </div>
  `;
}

function renderModel(model) {
  const reports = RESULTS[model] || {};
  const scenarios = Object.keys(reports).sort();
  const crumbs = `<div class="crumbs"><a onclick="clearSelection()">home</a> › ${escapeHtml(model)}</div>`;
  const t = modelTotals(model);
  return `
    ${crumbs}
    <h1>${escapeHtml(model)}</h1>
    <div class="stat-row">
      <div><b>${t.passed}</b>/${t.total} steps passed</div>
      <div><b>${scenarios.length}</b> scenarios</div>
    </div>
    <div class="scenario-grid">
      ${scenarios.map(s => {
        const r = reports[s];
        const cls = r.passed === r.total ? "pass" : (r.passed === 0 ? "fail" : "warn");
        return `<div class="card" onclick="selectPair('${model}','${s}')">
          <h3>${escapeHtml(s)}</h3>
          <div class="meta">
            <span class="pill ${cls}">${r.passed}/${r.total}</span>
            <span style="margin-left:8px">${(r.total_elapsed_s ?? 0).toFixed(1)}s · ${(r.total_tokens ?? 0).toLocaleString()} tok</span>
          </div>
        </div>`;
      }).join("") || '<div class="empty">no reports</div>'}
    </div>
  `;
}

function renderScenario(scenarioKey) {
  const spec = SCENARIOS[scenarioKey];
  const crumbs = `<div class="crumbs"><a onclick="clearSelection()">home</a> › ${escapeHtml(scenarioKey)}</div>`;
  const modelsWithRuns = Object.keys(RESULTS).filter(m => RESULTS[m][scenarioKey]).sort();
  return `
    ${crumbs}
    <h1>${escapeHtml(scenarioKey)}</h1>
    <div class="subtitle">${spec.name || ""} · ${(spec.steps || []).length} steps · reset_between_steps: ${!!spec.reset_between_steps}</div>

    <div class="section">
      <h4>Steps</h4>
      ${(spec.steps || []).map(st => `
        <div class="step">
          <div class="step-head" onclick="this.parentElement.classList.toggle('open')">
            <span class="id">${escapeHtml(st.id)}</span>
            <span class="prompt">${escapeHtml(st.prompt)}</span>
            ${st.judge ? '<span class="pill muted">judged</span>' : ""}
            ${st.changes ? '<span class="pill muted">changes</span>' : ""}
          </div>
          <div class="step-body">
            ${st.judge ? renderJudgeSpec(st.judge) : ""}
            ${st.changes ? `<div class="section"><h4>Expected changes</h4><pre class="text">${escapeHtml(JSON.stringify(st.changes, null, 2))}</pre></div>` : ""}
          </div>
        </div>
      `).join("")}
    </div>

    <div class="section">
      <h4>Runs</h4>
      <div class="scenario-grid">
        ${modelsWithRuns.map(m => {
          const r = RESULTS[m][scenarioKey];
          const cls = r.passed === r.total ? "pass" : (r.passed === 0 ? "fail" : "warn");
          return `<div class="card" onclick="selectPair('${m}','${scenarioKey}')">
            <h3>${escapeHtml(m)}</h3>
            <div class="meta"><span class="pill ${cls}">${r.passed}/${r.total}</span></div>
          </div>`;
        }).join("") || '<div class="empty">no runs yet</div>'}
      </div>
    </div>
  `;
}

function renderPair(model, scenarioKey) {
  const spec = SCENARIOS[scenarioKey];
  const report = (RESULTS[model] || {})[scenarioKey];
  const crumbs = `<div class="crumbs">
    <a onclick="clearSelection()">home</a> ›
    <a onclick="selectModel('${model}')">${escapeHtml(model)}</a> ›
    ${escapeHtml(scenarioKey)}
  </div>`;
  if (!report) return `${crumbs}<div class="empty">no report for this pair</div>`;

  const specSteps = Object.fromEntries((spec.steps || []).map(s => [s.id, s]));
  const cls = report.passed === report.total ? "pass" : (report.passed === 0 ? "fail" : "warn");
  return `
    ${crumbs}
    <h1>${escapeHtml(model)} — ${escapeHtml(scenarioKey)}</h1>
    <div class="stat-row">
      <span class="pill ${cls}">${report.passed}/${report.total}</span>
      <div><b>${(report.total_elapsed_s ?? 0).toFixed(1)}</b>s</div>
      <div><b>${(report.total_tokens ?? 0).toLocaleString()}</b> tokens</div>
    </div>

    ${(report.steps || []).map(step => renderStep(step, specSteps[step.id])).join("")}
  `;
}

function renderStep(step, spec) {
  const cls = step.passed ? "pass" : "fail";
  const tokens = step.tokens ?? 0;
  const ms = step.elapsed_ms ?? 0;
  const toolCalls = step.tool_calls || [];
  const hasFailures = (step.tool_failures || []).length > 0;
  const hasDiffs = step.diffs && Object.keys(step.diffs).length > 0;
  return `
    <div class="step">
      <div class="step-head" onclick="this.parentElement.classList.toggle('open')">
        <span class="pill ${cls}">${step.passed ? "PASS" : "FAIL"}</span>
        <span class="id">${escapeHtml(step.id)}</span>
        <span class="prompt">${escapeHtml(step.prompt || (spec && spec.prompt) || "")}</span>
        <span class="sub" style="color:var(--muted);font-size:11px">${ms}ms · ${tokens.toLocaleString()}t</span>
        ${hasFailures ? '<span class="pill fail">tool-err</span>' : ""}
      </div>
      <div class="step-body">
        ${spec && spec.prompt ? `<div class="section"><h4>Prompt</h4><pre class="text">${escapeHtml(spec.prompt)}</pre></div>` : ""}
        ${toolCalls.length ? `<div class="section"><h4>Tool calls</h4><div class="tool-calls">${toolCalls.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div></div>` : ""}
        ${hasFailures ? `<div class="section"><h4>Tool failures</h4><pre class="text">${escapeHtml(JSON.stringify(step.tool_failures, null, 2))}</pre></div>` : ""}
        ${step.send_error ? `<div class="section"><h4>Send error</h4><pre class="text">${escapeHtml(step.send_error)}</pre></div>` : ""}
        ${step.final_text ? `<div class="section"><h4>Final text</h4><pre class="text">${escapeHtml(step.final_text)}</pre></div>` : ""}
        ${hasDiffs ? queueDiff(step.diffs) : ""}
        ${step.judge ? renderJudgeVerdict(step.judge, spec && spec.judge) : (spec && spec.judge ? renderJudgeSpec(spec.judge) : "")}
      </div>
    </div>
  `;
}

function renderJudgeSpec(j) {
  return `<div class="section">
    <h4>Judge criteria</h4>
    <div class="judge">
      <div><b>Expected:</b> ${escapeHtml(j.expected_behavior || "")}</div>
      ${(j.criteria || []).map(c => `<div class="crit">· ${escapeHtml(c)}</div>`).join("")}
    </div>
  </div>`;
}

function renderJudgeVerdict(verdict, spec) {
  const passed = verdict.passed;
  return `<div class="section">
    <h4>Judge verdict</h4>
    <div class="judge">
      <div><span class="pill ${passed ? 'pass' : 'fail'}">${passed ? 'PASS' : 'FAIL'}</span>
        <span style="color:var(--muted);margin-left:8px">${escapeHtml(verdict.model || "")}</span></div>
      <div style="margin-top:8px">${escapeHtml(verdict.reasoning || "")}</div>
      ${(verdict.failed_criteria || []).length ? `
        <div style="margin-top:8px;color:var(--fail)"><b>Failed criteria:</b>
          ${verdict.failed_criteria.map(c => `<div class="crit">· ${escapeHtml(c)}</div>`).join("")}
        </div>` : ""}
      ${spec ? `<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--muted)">criteria spec</summary>
        <div style="margin-top:6px">${(spec.criteria || []).map(c => `<div class="crit">· ${escapeHtml(c)}</div>`).join("")}</div>
      </details>` : ""}
    </div>
  </div>`;
}

renderNav();
renderMain();
</script>
</body>
</html>
"""


def main() -> None:
    scenarios = load_scenarios()
    results = load_results()

    def _safe(obj) -> str:
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    html = (
        HTML_TEMPLATE
        .replace("__SCENARIOS__", _safe(scenarios))
        .replace("__RESULTS__", _safe(results))
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    n_models = len(results)
    n_reports = sum(len(v) for v in results.values())
    print(f"wrote {OUTPUT.relative_to(ROOT)}  ({len(scenarios)} scenarios, {n_models} models, {n_reports} reports)")


if __name__ == "__main__":
    main()
