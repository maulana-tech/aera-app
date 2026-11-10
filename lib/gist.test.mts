import { test } from "node:test";
import assert from "node:assert/strict";

import { gist } from "./gist.ts";

/* The regressions this exists for. The old code's fallback ran
 * replace(/[#*_-]/g, " ") over the raw text, so every hyphen became a space
 * and the queue showed material codes and verbs that nobody had written. */
test("a hyphen inside a word is a hyphen, not a marker", () => {
  assert.equal(gist("Re-source M-4471 from the Thai mill."),
               "Re-source M-4471 from the Thai mill.");
  assert.equal(gist("Keep actual_idr and days_of_cover intact."),
               "Keep actual_idr and days_of_cover intact.");
});

/* Dropping the underscores from __urgent__ is not the same slip: CommonMark
 * really does read that as bold, so stripping it is reading markdown, not
 * mangling a word. The name that must survive is the snake_case one above,
 * and it does - a single underscore is never a marker. */
test("double underscores are bold, as markdown says", () => {
  assert.equal(gist("Treat D as __blocked__ on TKDN."), "Treat D as blocked on TKDN.");
});

test("markdown is stripped as markdown", () => {
  assert.equal(gist("**Order** from *Siam* with `qty 232.7`."),
               "Order from Siam with qty 232.7.");
  assert.equal(gist("See [the quotation](https://erp.example/6000000848) first."),
               "See the quotation first.");
  assert.equal(gist("- Split the order across B and C."),
               "Split the order across B and C.");
  assert.equal(gist("2) Hold E until the certificate clears."),
               "Hold E until the certificate clears.");
  assert.equal(gist("> Kira blocked D on TKDN."), "Kira blocked D on TKDN.");
});

test("a heading names a section and is not the gist", () => {
  assert.equal(gist("## Recommendation\n\nSplit the order across B and C."),
               "Split the order across B and C.");
});

test("the report's own furniture is skipped", () => {
  const raw = [
    "status: done",
    "Run: run_17",
    "Generated: 2026-10-28",
    "---",
    "| Option | Cost |",
    "Recommendation:",
    "Order B and C at Rp 116,000,000.",
  ].join("\n");
  assert.equal(gist(raw), "Order B and C at Rp 116,000,000.");
});

test("a fenced block carries no sentence", () => {
  assert.equal(gist("```json\n{\"qty\": 1.0}\n```\nQuantity covers 232.7 short."),
               "Quantity covers 232.7 short.");
});

test("short answers are answers", () => {
  assert.equal(gist("No cover."), "No cover.");
});

test("nothing in, nothing claimed", () => {
  assert.equal(gist(undefined), "");
  assert.equal(gist(""), "");
  assert.equal(gist("\n\n   \n"), "");
  assert.equal(gist("### Only a heading"), "");
});
