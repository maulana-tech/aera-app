// A dependency-free smoke check of what the app shows from agents (run in CI before the build):
// agents write Markdown, and outside text reaches it, so the renderer must drop raw HTML, scripted links and
// remote images; and a tool from outside AERA (an MCP server, an app through Composio) must read as borrowed.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Compile the shared TSX components in memory, so the check needs no build.
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
const { toolLabel, stageLabel, stepAgentName } = await import(await componentURL("agent-activity"));
const render = (Component, props) => renderToStaticMarkup(createElement(Component, props));

// what an agent writes renders as a document
const html = render(Markdown, { children: "## Market brief\n\n**Demand** for `brief`\n\n1. Research\n2. Write\n\n| Offering | Price |\n| --- | --- |\n| brief | $15 |" });
assert.match(html, /<h2>Market brief<\/h2>/);
assert.match(html, /<strong>Demand<\/strong>/);
assert.match(html, /<code[^>]*>brief<\/code>/);
assert.match(html, /<ol>/);
assert.match(html, /<table/);

// outside text cannot run, redirect or track through it
const unsafe = render(Markdown, { children: '<script>alert(1)</script>\n\n<img src="https://example.com/x.png">\n\n[click](javascript:alert(1))\n\n![tracking](https://example.com/pixel.png)' });
assert.doesNotMatch(unsafe, /<script/i, "raw HTML is dropped");
assert.doesNotMatch(unsafe, /javascript:/i, "a scripted link is neutralised");
assert.doesNotMatch(unsafe, /<img/i, "no remote image loads");
assert.match(unsafe, /tracking/, "an image keeps its alt text");

// tools from outside AERA read as borrowed, ours by name
assert.equal(toolLabel("mcp__sheets__append_row"), "Asking sheets (outside AERA): append row");
assert.equal(toolLabel("app__slack_send_message"), "Using Slack (outside AERA): send message");
assert.equal(toolLabel("ask_guardian"), "Consulting Guardian");
assert.equal(toolLabel("ask_prospector"), "Consulting prospector");
assert.equal(toolLabel("some_new_tool"), "some new tool");
assert.equal(stageLabel("specialist_done"), "Finding");
assert.equal(stageLabel("custom"), "Custom");
assert.equal(stepAgentName({ agent: "treasurer", agent_name: "x" }), "Treasurer");
assert.equal(stepAgentName({ agent: "writer", agent_name: "Writer" }), "Writer");

console.log("agent output ok: markdown renders ✓ · raw HTML, scripted links and remote images dropped ✓ · outside tools read as borrowed ✓");
