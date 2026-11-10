/* The first human sentence of a model's outcome.
 *
 * It lives in its own module, apart from the card that shows it, because it is
 * pure text handling with a history of getting it wrong - see the note on
 * gist() below - and a module is something `node --test` can hold still.
 */

/* Metadata lines an outcome may open with (status, run, generated...). Naming
 * them is a fact about the format rather than a guess at some model's voice. */
const METADATA = /^(status|kind|trigger|started|finished|run|event|mode|generated)\s*:/i;

/* The first human sentence of an outcome, for a work row's one or two lines.
 *
 * The status beside it already says where the work stands, so this only has
 * to give the gist. An earlier version tried much harder: it scored candidate
 * lines and carried a blacklist of specific agent phrasings. Guessing at one
 * model's voice is not something that can be kept correct, and its fallback
 * ran `replace(/[#*_-]/g, " ")` over the raw text, which turns every hyphen
 * into a space: "re-run" shipped as "re run".
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
