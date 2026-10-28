#!/usr/bin/env python3
"""The reference architecture diagram, drawn to scale from a layout.

    python3 sigap/architecture/diagram.py          # writes the .svg next to this file

Why a script and not a hand-drawn SVG: the coordinates are computed, so a box
cannot quietly overlap its neighbour or spill out of its parent when a label
changes. `check()` asserts both, and the generator refuses to write a diagram
that would be wrong. Edit the CONTENT section, run it again.

The style follows AWS's own reference-architecture convention: a group is a
labelled rectangle with an icon in its top-left corner, a service is a coloured
tile with a glyph, and the numbered squares are the steps of the flow — the
numbers are explained in ARCHITECTURE.md, not on the picture.

Colours are AWS's category palette, so a reader who knows those diagrams can
read this one without a legend: compute orange, storage green, database blue,
networking purple, AI teal, security red. SAP's own blue for the SAP group.
"""
from __future__ import annotations

import html
import pathlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

W, H = 1480, 980

# ----------------------------------------------------------------- palette
INK = "#16191F"          # text
MUTED = "#5A6471"        # secondary text
LINE = "#879196"         # connectors
AWSBOX = "#232F3E"       # the AWS Cloud frame
ACCOUNT = "#E7157B"      # an account boundary
VPC = "#8C4FFF"          # networking
COMPUTE = "#ED7100"      # EC2
STORAGE = "#7AA116"      # EBS / S3
DATABASE = "#527FFF"
AI = "#01A88D"           # Bedrock, AI Core
SECURITY = "#DD344C"     # IAM
SAPBLUE = "#0070F2"
GREY = "#5A6471"
STEP = "#1565C0"         # the numbered squares

FONT = "Arial, Helvetica, sans-serif"


# ------------------------------------------------------------------ layout
@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float
    name: str = ""

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    def contains(self, o: "Box") -> bool:
        return (self.x <= o.x and self.y <= o.y
                and self.x2 >= o.x2 and self.y2 >= o.y2)

    def overlaps(self, o: "Box") -> bool:
        return not (self.x2 <= o.x or o.x2 <= self.x
                    or self.y2 <= o.y or o.y2 <= self.y)


@dataclass
class Scene:
    parts: List[str] = field(default_factory=list)
    groups: List[Tuple[Box, Optional[Box]]] = field(default_factory=list)
    tiles: List[Tuple[Box, Optional[Box]]] = field(default_factory=list)
    overflow: List[str] = field(default_factory=list)

    def add(self, s: str) -> None:
        self.parts.append(s)


S = Scene()


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def text(x: float, y: float, t: str, size: float = 12, fill: str = INK,
         weight: str = "normal", anchor: str = "start", italic: bool = False) -> None:
    S.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
          f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}"'
          + (' font-style="italic"' if italic else "") + f'>{esc(t)}</text>')


def group(b: Box, label: str, colour: str, parent: Optional[Box] = None,
          dashed: bool = False, sub: str = "", icon: str = "") -> Box:
    """A labelled boundary, AWS style: the icon tile sits on the top-left corner."""
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    S.add(f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" rx="2" fill="none" '
          f'stroke="{colour}" stroke-width="2"{dash}/>')
    if icon:
        S.add(f'<rect x="{b.x}" y="{b.y}" width="34" height="34" fill="{colour}"/>')
        S.add(glyph(icon, b.x + 7, b.y + 7, 20, "#FFFFFF"))
        text(b.x + 44, b.y + 17, label, 14, colour, "bold")
        if sub:
            text(b.x + 44, b.y + 31, sub, 10.5, MUTED)
    else:
        text(b.x + 12, b.y + 19, label, 12.5, colour, "bold")
        if sub:
            text(b.x + 12, b.y + 33, sub, 10, MUTED)
    S.groups.append((b, parent))
    return b


#: Rough advance width of Arial as a fraction of the font size. Used only to
#: catch a label that would run out of its tile — a diagram's commonest rot.
CHAR = 0.55


def tile(b: Box, title: str, colour: str, icon: str, lines: Optional[List[str]] = None,
         parent: Optional[Box] = None) -> Box:
    """One service: a coloured icon square, a title, and supporting lines."""
    room = b.w - 56 - 8
    for t, size in [(title, 12)] + [(ln, 10) for ln in (lines or [])]:
        if len(t) * CHAR * size > room:
            S.overflow.append(f'"{t}" needs {len(t) * CHAR * size:.0f}px, tile has {room:.0f}px')
    S.add(f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" rx="3" fill="#FFFFFF" '
          f'stroke="#D5DBDB" stroke-width="1"/>')
    S.add(f'<rect x="{b.x + 10}" y="{b.y + 10}" width="38" height="38" rx="3" fill="{colour}"/>')
    S.add(glyph(icon, b.x + 18, b.y + 18, 22, "#FFFFFF"))
    text(b.x + 56, b.y + 26, title, 12, INK, "bold")
    for i, ln in enumerate(lines or []):
        text(b.x + 56, b.y + 42 + i * 13, ln, 10, MUTED)
    S.tiles.append((b, parent))
    return b


def step(x: float, y: float, n: int) -> None:
    """A numbered square. The numbers are explained in the document, not here."""
    S.add(f'<rect x="{x}" y="{y}" width="26" height="26" rx="2" fill="{STEP}"/>')
    S.add(f'<text x="{x + 13}" y="{y + 18}" font-family="{FONT}" font-size="14" '
          f'fill="#FFFFFF" font-weight="bold" text-anchor="middle">{n}</text>')


def link(points: List[Tuple[float, float]], both: bool = False, dashed: bool = False) -> None:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    back = ' marker-start="url(#arrowback)"' if both else ""
    S.add(f'<polyline points="{pts}" fill="none" stroke="{LINE}" stroke-width="1.6" '
          f'marker-end="url(#arrow)"{back}{dash}/>')


def glyph(kind: str, x: float, y: float, s: float, c: str) -> str:
    """Simplified service marks. Geometric on purpose: recognisable in the AWS
    idiom without passing themselves off as the official icon set."""
    g = {
        "cloud": f'<path d="M{x+2} {y+s*0.68} a{s*0.22} {s*0.22} 0 0 1 {s*0.08} -{s*0.42} '
                 f'a{s*0.3} {s*0.3} 0 0 1 {s*0.56} -{s*0.08} a{s*0.22} {s*0.22} 0 0 1 {s*0.18} {s*0.5} z" '
                 f'fill="{c}"/>',
        "chip": f'<rect x="{x+s*0.2}" y="{y+s*0.2}" width="{s*0.6}" height="{s*0.6}" rx="2" fill="{c}"/>'
                + "".join(f'<rect x="{x+s*(0.33+i*0.2)}" y="{y+s*0.02}" width="{s*0.08}" height="{s*0.16}" fill="{c}"/>'
                          f'<rect x="{x+s*(0.33+i*0.2)}" y="{y+s*0.82}" width="{s*0.08}" height="{s*0.16}" fill="{c}"/>'
                          f'<rect x="{x+s*0.02}" y="{y+s*(0.33+i*0.2)}" width="{s*0.16}" height="{s*0.08}" fill="{c}"/>'
                          f'<rect x="{x+s*0.82}" y="{y+s*(0.33+i*0.2)}" width="{s*0.16}" height="{s*0.08}" fill="{c}"/>'
                          for i in range(2)),
        "db": f'<ellipse cx="{x+s/2}" cy="{y+s*0.2}" rx="{s*0.36}" ry="{s*0.14}" fill="{c}"/>'
              f'<path d="M{x+s*0.14} {y+s*0.2} v{s*0.6} a{s*0.36} {s*0.14} 0 0 0 {s*0.72} 0 v-{s*0.6} z" fill="{c}"/>',
        "disk": f'<rect x="{x+s*0.08}" y="{y+s*0.14}" width="{s*0.84}" height="{s*0.72}" rx="3" fill="{c}"/>'
                f'<circle cx="{x+s/2}" cy="{y+s/2}" r="{s*0.16}" fill="#FFFFFF" opacity="0.9"/>',
        "ai": f'<circle cx="{x+s*0.3}" cy="{y+s*0.3}" r="{s*0.14}" fill="{c}"/>'
              f'<circle cx="{x+s*0.74}" cy="{y+s*0.24}" r="{s*0.1}" fill="{c}"/>'
              f'<circle cx="{x+s*0.68}" cy="{y+s*0.72}" r="{s*0.16}" fill="{c}"/>'
              f'<circle cx="{x+s*0.22}" cy="{y+s*0.76}" r="{s*0.1}" fill="{c}"/>'
              f'<path d="M{x+s*0.3} {y+s*0.3} L{x+s*0.74} {y+s*0.24} M{x+s*0.3} {y+s*0.3} '
              f'L{x+s*0.68} {y+s*0.72} M{x+s*0.22} {y+s*0.76} L{x+s*0.68} {y+s*0.72}" '
              f'stroke="{c}" stroke-width="{s*0.06}"/>',
        "users": f'<circle cx="{x+s*0.3}" cy="{y+s*0.28}" r="{s*0.16}" fill="{c}"/>'
                 f'<path d="M{x+s*0.06} {y+s*0.86} a{s*0.24} {s*0.26} 0 0 1 {s*0.48} 0 z" fill="{c}"/>'
                 f'<circle cx="{x+s*0.72}" cy="{y+s*0.32}" r="{s*0.13}" fill="{c}" opacity="0.75"/>'
                 f'<path d="M{x+s*0.52} {y+s*0.86} a{s*0.2} {s*0.22} 0 0 1 {s*0.4} 0 z" fill="{c}" opacity="0.75"/>',
        "net": f'<rect x="{x+s*0.36}" y="{y+s*0.04}" width="{s*0.28}" height="{s*0.22}" rx="2" fill="{c}"/>'
               + "".join(f'<rect x="{x+s*(0.04+i*0.36)}" y="{y+s*0.72}" width="{s*0.24}" height="{s*0.22}" rx="2" fill="{c}"/>'
                         for i in range(3))
               + f'<path d="M{x+s*0.5} {y+s*0.26} v{s*0.2} M{x+s*0.16} {y+s*0.72} v-{s*0.12} '
                 f'h{s*0.68} v{s*0.12} M{x+s*0.5} {y+s*0.46} v{s*0.14}" stroke="{c}" '
                 f'stroke-width="{s*0.06}" fill="none"/>',
        "shield": f'<path d="M{x+s/2} {y+s*0.04} L{x+s*0.9} {y+s*0.22} v{s*0.3} '
                  f'q0 {s*0.3} -{s*0.4} {s*0.44} q-{s*0.4} -{s*0.14} -{s*0.4} -{s*0.44} '
                  f'v-{s*0.3} z" fill="{c}"/>',
        "feed": f'<circle cx="{x+s*0.24}" cy="{y+s*0.76}" r="{s*0.1}" fill="{c}"/>'
                + "".join(f'<path d="M{x+s*0.24} {y+s*(0.52-i*0.22)} a{s*(0.24+i*0.22)} {s*(0.24+i*0.22)} 0 0 1 '
                          f'{s*(0.24+i*0.22)} {s*(0.24+i*0.22)}" stroke="{c}" stroke-width="{s*0.09}" fill="none"/>'
                          for i in range(2)),
        "factory": f'<path d="M{x+s*0.06} {y+s*0.9} v-{s*0.4} l{s*0.26} {s*0.18} v-{s*0.18} '
                   f'l{s*0.26} {s*0.18} v-{s*0.18} l{s*0.26} {s*0.18} v-{s*0.56} h{s*0.14} '
                   f'v{s*0.78} z" fill="{c}"/>',
        "doc": f'<path d="M{x+s*0.18} {y+s*0.06} h{s*0.42} l{s*0.22} {s*0.22} v{s*0.66} h-{s*0.64} z" fill="{c}"/>'
               + "".join(f'<rect x="{x+s*0.28}" y="{y+s*(0.44+i*0.14)}" width="{s*0.36}" '
                         f'height="{s*0.06}" fill="#FFFFFF"/>' for i in range(3)),
        "gear": f'<circle cx="{x+s/2}" cy="{y+s/2}" r="{s*0.3}" fill="{c}"/>'
                f'<circle cx="{x+s/2}" cy="{y+s/2}" r="{s*0.12}" fill="#FFFFFF"/>'
                + "".join(f'<rect x="{x+s*0.44}" y="{y+s*0.02}" width="{s*0.12}" height="{s*0.2}" '
                          f'fill="{c}" transform="rotate({a} {x+s/2} {y+s/2})"/>' for a in (0, 60, 120, 180, 240, 300)),
        "code": f'<rect x="{x+s*0.04}" y="{y+s*0.14}" width="{s*0.92}" height="{s*0.72}" rx="3" fill="{c}"/>'
                f'<path d="M{x+s*0.3} {y+s*0.38} l-{s*0.12} {s*0.12} l{s*0.12} {s*0.12} '
                f'M{x+s*0.7} {y+s*0.38} l{s*0.12} {s*0.12} l-{s*0.12} {s*0.12}" '
                f'stroke="#FFFFFF" stroke-width="{s*0.07}" fill="none"/>',
        "mail": f'<rect x="{x+s*0.06}" y="{y+s*0.2}" width="{s*0.88}" height="{s*0.6}" rx="2" fill="{c}"/>'
                f'<path d="M{x+s*0.06} {y+s*0.22} L{x+s/2} {y+s*0.54} L{x+s*0.94} {y+s*0.22}" '
                f'stroke="#FFFFFF" stroke-width="{s*0.07}" fill="none"/>',
        "scale": f'<path d="M{x+s/2} {y+s*0.08} v{s*0.78} M{x+s*0.2} {y+s*0.86} h{s*0.6} '
                 f'M{x+s*0.16} {y+s*0.26} h{s*0.68}" stroke="{c}" stroke-width="{s*0.08}" fill="none"/>'
                 f'<path d="M{x+s*0.02} {y+s*0.5} h{s*0.28} l-{s*0.14} -{s*0.24} z" fill="{c}"/>'
                 f'<path d="M{x+s*0.7} {y+s*0.5} h{s*0.28} l-{s*0.14} -{s*0.24} z" fill="{c}"/>',
    }
    return g[kind]


# ================================================================== CONTENT

def build() -> None:
    S.add(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')

    # ---------------------------------------------------------- the world
    world = group(Box(16, 16, 270, 854), "Indonesian manufacturer", GREY,
                  sub="plants · ports · suppliers", icon="factory")

    people = group(Box(32, 70, 238, 118), "People", GREY, world, dashed=True)
    tile(Box(44, 100, 214, 76), "Planner · Buyer", GREY, "users",
         ["Procurement lead · Admin", "limits checked server-side"], people)
    step(238, 60, 7)

    tile(Box(32, 212, 238, 92), "SAP S/4HANA Cloud", SAPBLUE, "db",
         ["stock · BOM · purchase orders", "customer orders · suppliers"], world)
    step(242, 196, 2)

    tile(Box(32, 322, 238, 80), "Master data upload", STORAGE, "doc",
         ["CSV per entity, when there", "is no SAP key"], world)

    feeds = group(Box(32, 428, 238, 208), "Public feeds", GREY, world, dashed=True,
                  sub="no credential, cached, timestamped")
    tile(Box(44, 478, 214, 68), "BMKG · GDACS", GREY, "feed",
         ["NASA EONET · USGS"], feeds)
    tile(Box(44, 556, 214, 68), "Open-Meteo", GREY, "feed",
         ["Google News · Nager.Date"], feeds)
    step(238, 418, 1)

    tile(Box(32, 660, 238, 80), "Rule pack", SECURITY, "scale",
         ["TKDN floor · LARTAS · leave", "signed off by a person"], world)

    tile(Box(32, 762, 238, 88), "Suppliers · customers", GREY, "mail",
         ["approved outreach only,", "never sent by an agent alone"], world)

    # ------------------------------------------------------------ AWS box
    aws = group(Box(306, 16, 820, 854), "AWS Cloud", AWSBOX,
                sub="ap-southeast-2", icon="cloud")

    acct = group(Box(346, 76, 760, 620), "Account", ACCOUNT, aws, icon="shield",
                 sub="the EC2 instance role grants Bedrock — no key on disk")

    vpc = group(Box(376, 132, 500, 470), "Virtual private cloud (VPC)", VPC, acct)

    ec2 = group(Box(396, 188, 460, 396), "Amazon EC2 · Ubuntu x86_64", COMPUTE, vpc,
                sub="systemd: sigap-agent, sigap-web")

    tile(Box(416, 244, 205, 82), "Nginx + TLS", VPC, "net",
         ["sigap.lumbungstack.dev", "acy.lumbungstack.dev"], ec2)
    tile(Box(631, 244, 205, 82), "sigap-web :3000", VPC, "code",
         ["Next.js 16 · React 19", "server components only"], ec2)

    tile(Box(416, 346, 420, 96), "sigap-agent :8787", COMPUTE, "gear",
         ["One Python process, standard library only.",
          "The HTTP service, the twelve agents, the",
          "schedule and its eight jobs, the workers."], ec2)
    step(820, 332, 3)

    tile(Box(526, 462, 200, 84), "Amazon EBS", STORAGE, "disk",
         ["SQLite, one file", "/var/lib/sigap/sigap.db"], ec2)
    step(730, 452, 8)

    br = group(Box(896, 132, 190, 470), "Amazon Bedrock", AI, acct,
               sub="resolved per call")
    tile(Box(908, 186, 166, 92), "Claude", AI, "ai",
         ["the deciders:", "Arya and Kira ⚖️"], br)
    tile(Box(908, 294, 166, 104), "Specialists", AI, "ai",
         ["MiniMax · DeepSeek", "Kimi · Qwen · GLM", "cheaper, same law"], br)
    tile(Box(908, 414, 166, 80), "IAM role", SECURITY, "shield",
         ["on the instance,", "no key on disk"], br)
    step(1058, 160, 4)

    integ = group(Box(346, 724, 760, 112), "Open to other agents", AWSBOX, aws, dashed=True)
    tile(Box(366, 758, 350, 70), "AgentCore Gateway", AI, "net",
         ["reads the registry as MCP", "over POST /mcp"], integ)
    tile(Box(736, 758, 350, 70), "46 tools, one registry", AWSBOX, "code",
         ["every reply carries its origin;", "missing is an error, not a value"], integ)
    step(690, 712, 6)

    # ------------------------------------------------------------ SAP box
    sap = group(Box(1146, 16, 318, 680), "SAP BTP", SAPBLUE, sub="the organisers' platform",
                icon="cloud")
    tile(Box(1162, 82, 286, 96), "SAP AI Core", SAPBLUE, "ai",
         ["gpt-5.4 — a second brain", "that spends no AWS credit"], sap)
    tile(Box(1162, 190, 286, 86), "sap-rpt-1.6", SAPBLUE, "ai",
         ["tabular prediction: Vega's", "delivery-slip ranking"], sap)
    step(1420, 70, 5)

    tile(Box(1162, 296, 286, 86), "SAP Joule", SAPBLUE, "users",
         ["asks SIGAP in plain language,", "cannot approve anything"], sap)
    tile(Box(1162, 394, 286, 96), "A2A bridge", SAPBLUE, "code",
         ["FastAPI + a2a-sdk, three", "read-only skills, 60 s budget"], sap)
    tile(Box(1162, 502, 286, 86), "Cloud Foundry", SAPBLUE, "cloud",
         ["cf push — the alternative", "home for the agent service"], sap)
    text(1162, 644, "SQLite on Cloud Foundry is reset on every restart.", 10, MUTED)
    text(1162, 660, "The approvals table is the official record, so that", 10, MUTED)
    text(1162, 676, "platform is for the demo. Postgres before anything real.", 10, MUTED)

    # --------------------------------------------------------- CI/CD box
    gh = group(Box(1146, 726, 318, 124), "GitHub Actions", GREY, dashed=True)
    tile(Box(1162, 762, 286, 76), "CI on every branch", GREY, "code",
         ["lint · 56 self-checks · SSH transport", "deploy from main, over SSH"], gh)

    # ------------------------------------------------------------- what leaves
    out = group(Box(16, 886, 1448, 78), "What leaves SIGAP", GREY, dashed=True)
    tile(Box(32, 906, 340, 48), "Email", DATABASE, "mail",
         ["Composio Gmail or SMTP"], out)
    tile(Box(384, 906, 340, 48), "Slack · Telegram · webhook", DATABASE, "net",
         ["team channels"], out)
    tile(Box(736, 906, 340, 48), "PDF · Excel", DATABASE, "doc",
         ["written by hand, stdlib"], out)
    tile(Box(1088, 906, 360, 48), "SAP writes", SAPBLUE, "db",
         ["approved actions only, idempotent"], out)
    step(1420, 872, 9)

    # ------------------------------------------------------------ connectors
    # feeds and SAP reads come in through the left channel
    link([(270, 248), (322, 248), (322, 394), (416, 394)], both=True)
    link([(270, 532), (334, 532), (334, 410), (416, 410)])
    # a person reaches the web app, the web app reaches the agent
    link([(270, 138), (300, 138), (300, 285), (416, 285)])
    link([(733, 326), (733, 346)], both=True)
    link([(621, 285), (631, 285)])
    # the agent calls Bedrock, and writes the record
    link([(836, 394), (896, 394)], both=True)
    link([(626, 442), (626, 462)], both=True)
    # the agent reaches SAP AI Core; Joule reaches back through the bridge
    link([(836, 420), (866, 420), (866, 616), (1146, 616)], both=True)
    # MCP
    link([(560, 584), (560, 758)], both=True)
    # Deploy comes from outside AWS, so it is routed round the boxes rather than
    # through them: down the strip right of the account, along the corridor
    # between the account and the integrations box, then up into EC2.
    link([(1146, 788), (1116, 788), (1116, 710), (880, 710), (880, 620),
          (626, 620), (626, 584)], dashed=True)
    # out
    link([(560, 836), (560, 886)])
    # rule pack into the agent
    link([(270, 700), (310, 700), (310, 426), (416, 426)])


def check() -> None:
    """A diagram that is wrong is worse than no diagram. Three things are
    asserted: nothing escapes the group it was declared inside, no two tiles in
    the same group overlap, and no label runs out of its tile. All three are how
    a layout silently rots when a label grows."""
    problems: List[str] = list(S.overflow)
    for b, parent in S.groups + S.tiles:
        if parent and not parent.contains(b):
            problems.append(f"{b!r} escapes its parent {parent!r}")
        if not Box(0, 0, W, H).contains(b):
            problems.append(f"{b!r} falls outside the canvas")
    tiles = [(b, p) for b, p in S.tiles]
    for i, (a, pa) in enumerate(tiles):
        for b, pb in tiles[i + 1:]:
            if pa is pb and a.overlaps(b):
                problems.append(f"{a!r} overlaps {b!r}")
    if problems:
        raise SystemExit("layout is wrong:\n  " + "\n  ".join(problems))
    print(f"layout ok · {len(S.groups)} groups · {len(S.tiles)} tiles")


def render() -> str:
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" font-family="{FONT}">\n'
        '<!-- SIGAP reference architecture. Generated by sigap/architecture/diagram.py;\n'
        '     edit the CONTENT section there and run it again rather than this file. -->\n'
        '<defs>'
        f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0 L10 5 L0 10 z" fill="{LINE}"/></marker>'
        f'<marker id="arrowback" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M10 0 L0 5 L10 10 z" fill="{LINE}"/></marker>'
        '</defs>\n'
    )
    return head + "\n".join(S.parts) + "\n</svg>\n"


if __name__ == "__main__":
    build()
    check()
    out = pathlib.Path(__file__).resolve().parent / "sigap-aws-architecture.svg"
    out.write_text(render())
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
