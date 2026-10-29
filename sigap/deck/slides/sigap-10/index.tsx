/**
 * SIGAP — ten pages, on the organiser's template.
 *
 * Every page is the organiser's 1920x1080 artwork with our content laid into
 * the space it leaves. That space is a wedge, not a rectangle: a purple
 * gradient climbs from the bottom right, so dark text is legible to x=1032
 * above y=500 and only to x=768 below it. Those numbers, and the four boxes
 * the organiser's own logos occupy, were measured off the image rather than
 * guessed — see ../../template/README.md and measure.py beside it.
 *
 * Anything that needs the full width sits on a white card (page 5), and
 * anything placed over the gradient is white text (ZONE.gradient).
 *
 * English, and deliberately plain: a judge should not have to know Indonesian
 * procurement law to follow it, so TKDN and LARTAS are named once and then
 * spoken of as local content and import restrictions.
 */
import type { DesignSystem, Page, SlideMeta } from '@open-slide/core';
import { useSlidePageNumber } from '@open-slide/core';
import type { CSSProperties, ReactNode } from 'react';

import architecture from './assets/architecture.svg';
import template from './assets/template.png';

export const design: DesignSystem = {
  palette: { bg: '#FFFFFF', text: '#15171A', accent: '#E5484D' },
  fonts: {
    display: '-apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif',
    body: '-apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif',
  },
  typeScale: { hero: 132, body: 27 },
  radius: 12,
};

const ink = {
  body: '#3C4149',
  muted: '#6A7079',
  rule: '#D9DCE1',
  red: '#E5484D',
  onDark: 'rgba(255,255,255,0.92)',
  onDarkMuted: 'rgba(255,255,255,0.72)',
};

const mono = '"SF Mono", ui-monospace, Menlo, Consolas, monospace';

/** Measured off assets/template.png. Do not nudge these by eye. */
const ZONE = {
  wide: { left: 80, top: 240, width: 952 },   // white to x=1032, above y=500
  tall: { left: 80, width: 688 },             // white to x=768, below y=500
  gradient: { left: 1120, width: 660 },       // white text only
  bottom: 856,
};

const fill: CSSProperties = {
  width: '100%',
  height: '100%',
  position: 'relative',
  color: 'var(--osd-text)',
  fontFamily: 'var(--osd-font-body)',
  backgroundImage: `url(${template})`,
  backgroundSize: '1920px 1080px',
  backgroundRepeat: 'no-repeat',
};

/* The page number has to dodge the partner logos (x<=576, y>=912) and the
 * photo (x>=1460, y>=834). The gap between them is white to about x=776. */
const Footer = ({ label }: { label: string }) => {
  const { current, total } = useSlidePageNumber();
  return (
    <div
      style={{
        position: 'absolute', left: 80, top: 872, width: 688,
        display: 'flex', justifyContent: 'space-between',
        fontSize: 18, color: ink.muted, letterSpacing: '0.04em',
      }}
    >
      <span>SIGAP · {label}</span>
      <span style={{ fontFamily: mono }}>
        {String(current).padStart(2, '0')} / {String(total).padStart(2, '0')}
      </span>
    </div>
  );
};

const Eyebrow = ({ children }: { children: ReactNode }) => (
  <div style={{
    fontSize: 20, fontWeight: 800, letterSpacing: '0.17em',
    textTransform: 'uppercase', color: ink.red,
  }}>{children}</div>
);

const Title = ({ children, size = 62 }: { children: ReactNode; size?: number }) => (
  <h1 style={{
    margin: '16px 0 0', fontSize: size, lineHeight: 1.04, fontWeight: 800,
    letterSpacing: '-0.022em', color: 'var(--osd-text)',
  }}>{children}</h1>
);

const Rule = ({ width = 110 }: { width?: number }) => (
  <div style={{ width, height: 4, background: ink.red, margin: '26px 0 0' }} />
);

const Body = ({ children, style }: { children: ReactNode; style?: CSSProperties }) => (
  <p style={{ margin: 0, fontSize: 26, lineHeight: 1.5, color: ink.body, ...style }}>
    {children}
  </p>
);

const Small = ({ children, style }: { children: ReactNode; style?: CSSProperties }) => (
  <p style={{ margin: 0, fontSize: 20, lineHeight: 1.45, color: ink.muted, ...style }}>
    {children}
  </p>
);

/** A labelled step in the narrow white column. */
const Step = ({ n, head, children }: { n: string; head: string; children: ReactNode }) => (
  <div style={{ display: 'flex', gap: 20, alignItems: 'baseline' }}>
    <span style={{
      fontFamily: mono, fontSize: 18, color: ink.red, fontWeight: 700, minWidth: 26,
    }}>{n}</span>
    <div>
      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--osd-text)' }}>{head}</div>
      <div style={{ fontSize: 21, lineHeight: 1.45, color: ink.muted, marginTop: 4 }}>
        {children}
      </div>
    </div>
  </div>
);

/** One feature in a 2x2 grid. The white column is 688 wide, so two columns of
 *  324 with a 40 gutter — the same split as template/sheets/04-two-column. */
const Card = ({ head, children }: { head: string; children: ReactNode }) => (
  <div>
    <div style={{ fontSize: 23, fontWeight: 800, lineHeight: 1.2 }}>{head}</div>
    <div style={{ fontSize: 20, lineHeight: 1.42, color: ink.muted, marginTop: 7 }}>
      {children}
    </div>
  </div>
);

/** One claim on the gradient, in white. */
const OnGradient = ({ top, kicker, children, sub }:
  { top: number; kicker?: string; children: ReactNode; sub?: ReactNode }) => (
  <div style={{ position: 'absolute', left: ZONE.gradient.left, top, width: ZONE.gradient.width }}>
    {kicker && (
      <div style={{
        fontSize: 18, fontWeight: 800, letterSpacing: '0.16em',
        textTransform: 'uppercase', color: ink.onDarkMuted, marginBottom: 14,
      }}>{kicker}</div>
    )}
    <div style={{ fontSize: 34, lineHeight: 1.3, fontWeight: 700, color: '#fff' }}>
      {children}
    </div>
    {sub && (
      <div style={{ fontSize: 21, lineHeight: 1.45, color: ink.onDarkMuted, marginTop: 16 }}>
        {sub}
      </div>
    )}
  </div>
);

const Pill = ({ children, red = false }: { children: ReactNode; red?: boolean }) => (
  <span style={{
    display: 'inline-block', fontSize: 19, fontWeight: 700, padding: '6px 16px',
    borderRadius: 999, marginRight: 10,
    color: red ? ink.red : 'var(--osd-text)',
    border: `2px solid ${red ? ink.red : '#15171A'}`,
  }}>{children}</span>
);

/* ------------------------------------------------------------------ pages */

const Cover: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 272, width: ZONE.wide.width }}>
      <Eyebrow>SAP + AWS Agentic AI Hackathon 2026 · Supply Chain</Eyebrow>
      <div style={{
        fontSize: 'var(--osd-size-hero)', fontWeight: 800, letterSpacing: '-0.035em',
        lineHeight: 0.94, marginTop: 20,
      }}>SIGAP</div>
      <Rule width={150} />
      <h2 style={{
        margin: '28px 0 0', fontSize: 42, lineHeight: 1.14, fontWeight: 700,
        letterSpacing: '-0.015em', maxWidth: 660,
      }}>
        Supply disruptions handled before anyone has to notice
      </h2>
      <Body style={{ marginTop: 24, maxWidth: 640, fontSize: 24 }}>
        Twelve agents read your SAP data, obey Indonesia&rsquo;s local-content and
        import rules, and put one decision you can approve on your desk.
      </Body>
      <div style={{ marginTop: 32 }}>
        <Pill>Team Socrates</Pill>
        <Pill>APP Group</Pill>
        <Pill red>Live demo</Pill>
      </div>
    </div>
  </div>
);

const Problem: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>01 · The problem</Eyebrow>
      <Title>A port closes Monday. The decision lands Thursday.</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 476, width: ZONE.tall.width,
      display: 'grid', gap: 26,
    }}>
      <Step n="1" head="The news arrives on the wrong channel">
        A headline, a WhatsApp group, a call from the forwarder.
      </Step>
      <Step n="2" head="Three days of tracing it by hand">
        Excel, email, asking around: which orders are actually hit?
      </Step>
      <Step n="3" head="The decision is made on stale data">
        The numbers already moved on Tuesday.
      </Step>
      <Step n="4" head="Then the reasoning disappears">
        Nothing records why. An audit becomes archaeology.
      </Step>
    </div>
    <OnGradient top={470} kicker="Where the money actually goes">
      The fastest decision is often the one that was never allowed.
      <span style={{ display: 'block', marginTop: 18, fontSize: 24, fontWeight: 400 }} />
    </OnGradient>
    <OnGradient top={660} kicker="" sub="The data is already in S/4HANA. What is missing are the hours between the signal and the decision.">
      <span style={{ fontSize: 26, fontWeight: 400, color: ink.onDark }}>
        This is not a missing-ERP problem.
      </span>
    </OnGradient>
    <Footer label="The problem" />
  </div>
);

const Rules: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>01 · The problem</Eyebrow>
      <Title>Two Indonesian rules that make the cheapest option illegal</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 506, width: ZONE.tall.width,
      display: 'grid', gap: 30,
    }}>
      <div>
        <div style={{ fontSize: 27, fontWeight: 800 }}>TKDN — local content</div>
        <Small style={{ marginTop: 6, fontSize: 22 }}>
          Regulation and most contracts set a floor on how much must be made in
          Indonesia. Switching to an imported supplier pushes you under it.
        </Small>
      </div>
      <div>
        <div style={{ fontSize: 27, fontWeight: 800 }}>LARTAS — import restrictions</div>
        <Small style={{ marginTop: 6, fontSize: 22 }}>
          A new country of origin needs permits, and permits do not arrive in a
          week.
        </Small>
      </div>
      <div style={{ borderTop: `1px solid ${ink.rule}`, paddingTop: 22 }}>
        <Small style={{ fontSize: 21 }}>
          Making the decision faster without enforcing these two is not progress.
          It is faster contract breach.
        </Small>
      </div>
    </div>
    <OnGradient
      top={520}
      kicker="From the live demo"
      sub="Not because it costs too much. Because it is not allowed — and a price cannot overrule a rule.">
      Option E — Rp 48 million, the cheapest — is struck out.
      <span style={{ display: 'block', marginTop: 14, fontSize: 28, fontWeight: 400, color: ink.onDarkMuted }}>
        Local content falls to 34.8%.
      </span>
    </OnGradient>
    <Footer label="The problem" />
  </div>
);

const Solution: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>02 · The solution</Eyebrow>
      <Title>Twelve agents, one decision you can sign</Title>
      <Rule />
    </div>
    {/* Five steps have to clear the partner logos at y=912, so they start
        higher and sit tighter than the four-step pages. */}
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 452, width: ZONE.tall.width,
      display: 'grid', gap: 16,
    }}>
      <Step n="01" head="It watches instead of waiting">
        Public hazard feeds, every few minutes, nobody asked.
      </Step>
      <Step n="02" head="Twelve agents read the real data">
        S/4HANA, master data, your uploads, the feeds.
      </Step>
      <Step n="03" head="Kira strikes out what is not allowed">
        Local content and import rules, before price gets a turn.
      </Step>
      <Step n="04" head="Tara puts a number on each option">
        Cost, stock-out date, arrival date, local-content impact.
      </Step>
      <Step n="05" head="It acts inside its authority">
        Above that limit it stops and asks a person.
      </Step>
    </div>
    <OnGradient
      top={500}
      kicker="One agent holds a veto"
      sub="The veto is code reading a rule pack, not a prompt. A cheaper option cannot talk its way past it.">
      Kira blocks at two gates — when the option is chosen, and again when the PO is issued.
    </OnGradient>
    <Footer label="The solution" />
  </div>
);

const Architecture: Page = () => (
  <div style={fill}>
    {/* The diagram needs the full band, which only a white card can give. */}
    <div style={{
      position: 'absolute', left: 80, top: 240, width: 1760, height: 616,
      background: 'rgba(255,255,255,0.97)', borderRadius: 'var(--osd-radius)',
      boxShadow: '0 18px 60px rgba(60,20,90,0.16)',
    }} />
    <div style={{ position: 'absolute', left: 136, top: 286, width: 1000 }}>
      <Eyebrow>03 · Architecture</Eyebrow>
      <h1 style={{
        margin: '12px 0 0', fontSize: 44, fontWeight: 800, letterSpacing: '-0.02em',
      }}>
        AWS for the thinking, SAP for the data and the doors
      </h1>
    </div>
    <img
      src={architecture}
      alt="SIGAP architecture: Amazon Bedrock and AgentCore on the model side, SAP S/4HANA and AI Core on the data side"
      style={{
        position: 'absolute', left: 136, top: 398, width: 1648, height: 398,
        objectFit: 'contain',
      }}
    />
    <div style={{ position: 'absolute', left: 136, top: 810, width: 1200 }}>
      <Small style={{ fontSize: 18 }}>
        Agent service: Python 3, standard library only — <span style={{ fontFamily: mono }}>http.server</span>{' '}
        + <span style={{ fontFamily: mono }}>sqlite3</span>. This diagram is generated by{' '}
        <span style={{ fontFamily: mono }}>sigap/architecture/diagram.py</span>, not drawn.
      </Small>
    </div>
  </div>
);

const Demo: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 380, width: ZONE.tall.width }}>
      <Eyebrow>Pause</Eyebrow>
      <div style={{
        fontSize: 108, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 0.96,
        marginTop: 18,
      }}>
        Demo
        <span style={{ color: ink.red }}>.</span>
      </div>
      <Rule />
      <Body style={{ marginTop: 26, fontSize: 24 }}>
        One typhoon closes Ningbo. Watch SIGAP find it, size it, strike out the
        cheapest option, and then stop to ask for a signature.
      </Body>
    </div>
    <OnGradient
      top={430}
      kicker="What you are about to see"
      sub="Every number on screen can be recomputed from the commands in DEMO.md.">
      Live, not a recording — against real SAP S/4HANA and Amazon Bedrock.
    </OnGradient>
  </div>
);

const Detect: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>04 · Detect</Eyebrow>
      <Title>It is already watching, all night</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 452, width: ZONE.tall.width,
      display: 'grid', gap: 18,
    }}>
      <Step n="01" head="Five public feeds, no licence needed">
        BMKG, GDACS, NASA EONET, USGS, Open-Meteo.
      </Step>
      <Step n="02" head="Eight jobs on their own clock">
        Quakes every five minutes; cyclones, floods and marine weather on theirs.
      </Step>
      <Step n="03" head="It watches your paperwork too">
        Local-content certificates that are about to expire, before they lapse.
      </Step>
      <Step n="04" head="One digest at 07:30">
        What moved overnight, and what is waiting for your signature.
      </Step>
    </div>
    <OnGradient
      top={500}
      kicker="Nothing to remember to check"
      sub="It only needs your ports, plants and material list: every event is matched against them by distance, so a quake 2,000 km away stays silent.">
      No inbox to watch, no dashboard to open, for SIGAP to start working.
    </OnGradient>
    <Footer label="Detect" />
  </div>
);

const Act: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>05 · Act</Eyebrow>
      <Title>It does the work, not just the advice</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 510, width: ZONE.tall.width,
      display: 'grid', gridTemplateColumns: '324px 324px', gap: '46px 40px',
    }}>
      <Card head="Buys inside a limit">
        Under Rp 50 million it moves on its own. Above it, it stops and asks.
        One setting, checked on the server.
      </Card>
      <Card head="Writes back into SAP">
        The approved action leaves as a purchase order — idempotent, and only
        ever after a person signs off.
      </Card>
      <Card head="Talks to your suppliers">
        It drafts the outreach email and holds it. No agent sends anything on
        its own.
      </Card>
      <Card head="Tells the right people">
        Email, Slack, Telegram, or a webhook for Teams and ticket queues.
      </Card>
    </div>
    <OnGradient
      top={500}
      kicker="Where it stops"
      sub="Approve, hold or reject — and the record keeps who did it, when, and on which figures.">
      Every action that leaves the building has a gate a human can hold shut.
    </OnGradient>
    <Footer label="Act" />
  </div>
);

const Open: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>06 · Open</Eyebrow>
      <Title>Built for other agents, not only for people</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 480, width: ZONE.tall.width,
      display: 'grid', gap: 0,
    }}>
      {[
        ['MCP', 'All 46 tools over one POST /mcp endpoint. AWS AgentCore Gateway speaks MCP, and so does SAP Joule.'],
        ['A2A', 'An agent card with three read-only skills: investigate a disruption, check how one is going, scan for risk. None of them can approve anything.'],
        ['Reports', 'PDF and Excel per handling, plus a portfolio view across all of them — written with the standard library, no reporting dependency.'],
      ].map(([label, copy], i) => (
        <div key={label} style={{
          display: 'flex', alignItems: 'baseline', gap: 24, padding: '13px 0',
          borderTop: i === 0 ? 'none' : `1px solid ${ink.rule}`,
        }}>
          <div style={{
            fontSize: 27, fontWeight: 800, letterSpacing: '-0.01em', minWidth: 132,
            color: ink.red,
          }}>{label}</div>
          <div style={{ fontSize: 20, lineHeight: 1.42, color: ink.muted }}>{copy}</div>
        </div>
      ))}
    </div>
    <OnGradient
      top={500}
      kicker="Why that matters here"
      sub="Ask Joule in plain language and the answer still carries where each figure came from — and Joule is not allowed to approve.">
      SIGAP is a teammate other agents can call, not an app you have to open.
    </OnGradient>
    <Footer label="Open" />
  </div>
);

const Closing: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 300, width: ZONE.tall.width }}>
      <Eyebrow>One sentence to remember</Eyebrow>
      <h1 style={{
        margin: '22px 0 0', fontSize: 50, lineHeight: 1.14, fontWeight: 800,
        letterSpacing: '-0.02em',
      }}>
        Not an agent that decides faster — an agent that refuses to decide what
        it may not.
      </h1>
      <Rule width={150} />
      <Body style={{ marginTop: 28, fontSize: 23 }}>
        A decision you can approve, with the origin of every figure behind it,
        in minutes — and never against local-content or import rules.
      </Body>
      <div style={{ marginTop: 30, fontFamily: mono, fontSize: 20, color: ink.muted }}>
        sigap.lumbungstack.dev
      </div>
    </div>
    <OnGradient
      top={470}
      kicker="Team Socrates"
      sub="Thank you — and please ask us to re-run any command whose numbers you saw on screen.">
      Ready for your questions.
    </OnGradient>
  </div>
);

/* ------------------------------------------------------------------ notes */

export const notes: (string | undefined)[] = [
  'Hello, we are Team Socrates. SIGAP: supply disruptions handled before anyone has to notice. Ten pages, one of them a live demo. Let me start with why this is hard.',
  'When a port closes, dozens of materials stop with it. The expensive part is not the typhoon. It is three days of Excel and WhatsApp to find out which orders are hit, then deciding on numbers that moved two days ago, with nothing recording why. The data is already in S/4HANA. What is missing are the hours between the signal and the decision.',
  'And there is a dimension that is specific to Indonesia. The cheapest replacement is almost always imported, and importing cuts your local-content score and runs into import restrictions. In the demo you will see option E, the cheapest at 48 million rupiah, struck out because local content falls to 34.8 per cent. Not because it costs too much. Because it is not allowed. So making the decision faster without enforcing these rules is not progress.',
  'SIGAP closes those hours. It watches public hazard feeds without being asked. Twelve agents read SAP and the supporting data. Kira strikes out what is not allowed before price gets a turn, and her veto sits at two gates: when the option is chosen, and again when the purchase order is issued. Tara puts a number on each surviving option. Then the system acts inside its authority, and stops to ask above it.',
  'The architecture: AWS for the thinking, Bedrock and AgentCore, and SAP for the data and the doors, S/4HANA and AI Core. The agent service is Python standard library only, http.server and sqlite3 — no orchestrator, no message broker. This diagram is generated from the code, not drawn by hand.',
  'Now the demo. One typhoon closes Ningbo. This is live against real SAP and real Bedrock. Watch three things: where each number comes from, where Kira strikes an option out, and where the system stops and asks for a signature.',
  'Let me show you the features behind what you just saw. First, detection. SIGAP watches five public feeds — BMKG for quakes in Indonesia, GDACS, NASA EONET, USGS and Open-Meteo — on eight scheduled jobs. It also watches your own paperwork: local-content certificates about to expire. And at half past seven every morning it sends one digest of what moved overnight. Nobody has to remember to check anything.',
  'Second, acting. Under 50 million rupiah it moves on its own; above that it stops and asks, and that limit is checked on the server, not in the prompt. The approved action leaves as a real purchase order into SAP. Supplier emails are drafted and held — no agent sends anything by itself. And the people who need to know are told, over email, Slack, Telegram or a webhook.',
  'Third, and this is the part we are proudest of in an agentic track: SIGAP is open. All 46 tools are exposed over a single MCP endpoint, which is what AWS AgentCore Gateway and SAP Joule both speak. There is an A2A agent card with three read-only skills, so another agent can hand SIGAP work. And every handling comes out as a PDF and an Excel file, with a portfolio view across all of them.',
  'One sentence to take away: this is not an agent that decides faster, it is an agent that refuses to decide what it may not. A decision you can approve, with the origin of every figure behind it, in minutes. Please ask us to re-run any command whose numbers you saw. Thank you.',
];

export const meta: SlideMeta = {
  title: 'SIGAP — 10 pages, organiser template',
  createdAt: '2026-10-29T00:34:00.000Z',
};

export default [
  Cover,
  Problem,
  Rules,
  Solution,
  Architecture,
  Demo,
  Detect,
  Act,
  Open,
  Closing,
] satisfies Page[];
