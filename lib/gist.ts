/* The first human sentence of a model's recommendation.
 *
 * It lives in its own module, apart from the card that shows it, because it is
 * pure text handling with a history of getting it wrong - see the note on
 * gist() below - and a module is something `node --test` can hold still.
 */

/* The report's own metadata lines. These come from engine/report.py, not from
 * a model, so naming them is a fact about our format rather than a guess at
 * some model's voice. */
const METADATA = /^(status|kind|trigger|started|finished|run|event|mode|generated)\s*:/i;

/* The first human sentence of a recommendation, for the card's two lines.
 *
 * The verdict above already says what is owed and what it is worth, so this
 * only has to give the gist. It used to try much harder: it scored candidate
 * lines, required 30 characters, and carried a blacklist of specific agent
 * phrasings ("Elsa has made the right call"). Guessing at one model's voice is
 * not something that can be kept correct, and the fallback path it fell into
 * ran `replace(/[#*_-]/g, " ")` over the raw text, which turns every hyphen
 * into a space: "re-source" shipped to the queue as "re source" and "M-4471"
 * as "M 4471".
 *
 * So it strips Markdown as Markdown - only where a character is a marker - and
 * takes the first line that carries content. Short answers are answers.
 */
export function gist(raw?: string): string {
  if (!raw) return "";
  const lines = raw
    .replace(/\r/g, "")
    .replace(/```[\s\S]*?```/g, " ")
    .split("\n");

  for (const line of lines) {
    const heading = /^\s*#{1,6}\s+/.test(line);
    const text = line
      .replace(/^\s*#{1,6}\s+/, "")
      .replace(/^\s*>\s?/, "")
      .replace(/^\s*[-*+]\s+/, "")
      .replace(/^\s*\d+[.)]\s+/, "")
      .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/__([^_]+)__/g, "$1")
      .replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s).,;:!?]|$)/g, "$1$2")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\s+/g, " ")
      .trim();

    if (!text) continue;
    if (heading) continue;                                  // names a section, is not the gist
    if (/^[-=_*]{3,}$/.test(text)) continue;                // horizontal rule
    if (text.startsWith("|")) continue;                     // table row
    if (METADATA.test(text)) continue;
    if (/^[A-Za-z][A-Za-z ]{1,24}:$/.test(text)) continue;  // a bare label, nothing after it
    return text;
  }
  return "";
}
