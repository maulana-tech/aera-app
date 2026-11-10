import { test } from "node:test";
import assert from "node:assert/strict";

import { gist } from "./gist.ts";

/* The regressions this exists for. An old fallback ran replace(/[#*_-]/g, " ")
 * over the raw text, so every hyphen became a space and the work list showed
 * ids and verbs that nobody had written. */
test("a hyphen inside a word is a hyphen, not a marker", () => {
  assert.equal(gist("Re-run the brief for ord-4471 with the fresh sources."),
               "Re-run the brief for ord-4471 with the fresh sources.");
  assert.equal(gist("Keep amount_usd and sla_hours intact."),
               "Keep amount_usd and sla_hours intact.");
});

/* Dropping the underscores from __urgent__ is not the same slip: CommonMark
 * really does read that as bold, so stripping it is reading markdown, not
 * mangling a word. The name that must survive is the snake_case one above,
 * and it does - a single underscore is never a marker. */
test("double underscores are bold, as markdown says", () => {
  assert.equal(gist("Treat the refund as __blocked__ by the guardian."),
               "Treat the refund as blocked by the guardian.");
});

test("markdown is stripped as markdown", () => {
  assert.equal(gist("**Delivered** the brief to *the customer* as `brief.pdf`."),
               "Delivered the brief to the customer as brief.pdf.");
  assert.equal(gist("See [the order](https://example.com/orders/ord_1) first."),
               "See the order first.");
  assert.equal(gist("- Pay the data vendor $12 once approved."),
               "Pay the data vendor $12 once approved.");
  assert.equal(gist("2) Hold the refund until a person signs it."),
               "Hold the refund until a person signs it.");
  assert.equal(gist("> Kira blocked the payout to an unknown account."),
               "Kira blocked the payout to an unknown account.");
});

test("a heading names a section and is not the gist", () => {
  assert.equal(gist("## Outcome\n\nThe brief was delivered within the SLA."),
               "The brief was delivered within the SLA.");
});

test("metadata lines are skipped", () => {
  const raw = [
    "status: done",
    "Run: run_17",
    "Generated: 2026-10-28",
    "---",
    "| Item | Cost |",
    "Outcome:",
    "Delivered ord_17 for $15.00.",
  ].join("\n");
  assert.equal(gist(raw), "Delivered ord_17 for $15.00.");
});

test("a fenced block carries no sentence", () => {
  assert.equal(gist("```json\n{\"amount_usd\": 1.0}\n```\nThe vendor was paid $1.00."),
               "The vendor was paid $1.00.");
});

test("short answers are answers", () => {
  assert.equal(gist("Nothing to do."), "Nothing to do.");
});

test("nothing in, nothing claimed", () => {
  assert.equal(gist(undefined), "");
  assert.equal(gist(""), "");
  assert.equal(gist("\n\n   \n"), "");
  assert.equal(gist("### Only a heading"), "");
});
