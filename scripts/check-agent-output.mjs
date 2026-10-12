import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Compile the shared TSX components in memory for a dependency-free smoke check.
const modules = new Map();
async function componentURL(name) {
  if (modules.has(name)) return modules.get(name);
  const source = await readFile(new URL(`../components/${name}.tsx`, import.meta.url), "utf8");
  let { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  });
  for (const match of [...outputText.matchAll(/from "([^"]+)"/g)]) {
    const specifier = match[1];
    const url = specifier.startsWith("@/components/")
      ? await componentURL(specifier.slice("@/components/".length))
      : import.meta.resolve(specifier);
    outputText = outputText.replace(`from "${specifier}"`, `from "${url}"`);
  }
  const url = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
  modules.set(name, url);
  return url;
}

const { Markdown } = await import(await componentURL("markdown"));
const { StepSummary, ToolActivity, stepAgentName, toolLabel, stageLabel } = await import(await componentURL("agent-activity"));
const render = (Component, props) => renderToStaticMarkup(createElement(Component, props));

const html = render(Markdown, { children: "## Finding\n\n**Stock** for `M-4471`\n\n1. Check orders\n2. Check stock\n\n| Item | Qty |\n| --- | --- |\n| M-4471 | 13 |" });
assert.match(html, /<h2>Finding<\/h2>/);
assert.match(html, /<strong>Stock<\/strong>/);
assert.match(html, /<code[^>]*>M-4471<\/code>/);
assert.match(html, /<ol>/);
assert.match(html, /<table/);
const unsafe = render(Markdown, { children: '<script>alert(1)</script>\n\n[click](javascript:alert(1))\n\n![tracking](https://example.com/pixel.png)' });
assert.doesNotMatch(unsafe, /<script|javascript:|<img/);
assert.equal(toolLabel("get_material_stock"), "Checking material stock");
assert.equal(toolLabel("ask_impact"), "Consulting Elsa");
assert.equal(toolLabel("unknown_tool"), "Running a system check");
assert.equal(toolLabel("constructor"), "Running a system check");
assert.equal(stageLabel("DELEGATE"), "Delegation");
assert.equal(stageLabel("TOOL"), "Data Check");
assert.equal(stageLabel("FINDING"), "Finding");
assert.equal(stepAgentName({ agent: "impact", agent_name: "get_material_stock" }), "Elsa");
assert.equal(render(ToolActivity, { tools: [] }), "");
const step = render(StepSummary, { step: { stage: "TOOL", summary: "get_material_stock", tools: ["get_material_stock"] } });
assert.match(step, /Checking material stock/);
assert.match(step, /<summary[^>]*>Activity details<\/summary>/);
assert.doesNotMatch(step, /get_material_stock/);
assert.match(render(StepSummary, { step: { stage: "FINDING", summary: "**13** materials", tools: [] } }), /<strong>13<\/strong> materials/);
console.log("Agent output checks passed: Markdown, safe rendering, activity details, and stage labels.");
