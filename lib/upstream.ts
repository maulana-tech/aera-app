/* Requests to the agent service, at most a few at a time.
 *
 * The service is a stdlib ThreadingHTTPServer whose listen backlog is five.
 * A page that reads ten things at once (the layout's three, plus a run
 * page's eight) overflows it, and the connections past the backlog are reset
 * before they are read: the page then says "not responding" for a service
 * that is fine. So every server-side call to it waits its turn here, and a
 * GET that is reset anyway is tried once more. A POST is never repeated,
 * because it may have been received. */

const MAX = 4;
let active = 0;
const waiting: (() => void)[] = [];

async function slot<T>(run: () => Promise<T>): Promise<T> {
  if (active >= MAX) await new Promise<void>((r) => waiting.push(r));
  active++;
  try {
    return await run();
  } finally {
    active--;
    waiting.shift()?.();
  }
}

export function upstream(url: string, init: RequestInit = {}): Promise<Response> {
  const once = () => slot(() => fetch(url, init));
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET") return once();
  return once().catch(() => new Promise((r) => setTimeout(r, 150)).then(once));
}
