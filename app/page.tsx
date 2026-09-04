import type { ReactNode } from "react";

const NAV = [
  { href: "#about", label: "About" },
  { href: "#tracks", label: "Tracks" },
  { href: "#join", label: "Who Can Join" },
  { href: "#why", label: "Why Join" },
  { href: "#prizes", label: "Prizes" },
  { href: "#register", label: "How to Register" },
  { href: "#contact", label: "Contact" },
];

const TRACKS = [
  {
    n: "01",
    title: "Intelligent Supply Chain",
    body: "Build an AI agent that solves a real business challenge in Supply Chain processes — from demand sensing and sourcing to disruption response and logistics.",
  },
  {
    n: "02",
    title: "Intelligent Manufacturing",
    body: "Build an AI agent that addresses a real business challenge in Manufacturing processes — from quality and maintenance to scheduling and shop-floor efficiency.",
  },
];

const WHY = [
  {
    icon: "🚀",
    title: "Build with Agentic AI",
    body: "Get hands-on experience building solutions using AWS and SAP technologies.",
  },
  {
    icon: "🎓",
    title: "Learn from the Experts",
    body: "Access learning resources, technical workshops and mentorship from AWS and SAP.",
  },
  {
    icon: "🛠",
    title: "Get the Tools to Build",
    body: "Finalist teams receive AWS & SAP learning resources, AWS & SAP BAIP accounts and free-tier credits, Kiro / SAP Joule, and technical documentation.",
  },
  {
    icon: "🌟",
    title: "Make Your Mark",
    body: "Show what you can build, connect with the technology ecosystem and gain recognition for your solution.",
  },
  {
    icon: "🏆",
    title: "Compete at Demo Day",
    body: "Take the stage at the Hackathon Finals and stand a chance to win a prize pool of more than IDR 130,000,000.",
  },
];

const PRIZES = [
  { place: "1st Winner", amount: "IDR 35,000,000", featured: true },
  { place: "2nd Winner", amount: "IDR 20,000,000", featured: false },
  { place: "3rd Winner", amount: "IDR 12,500,000", featured: false },
];

const SUBMISSION_RULES = [
  "Use AWS and/or SAP services and generative AI / agentic AI capabilities as the core of the solution",
  "Whenever possible, demonstrate a working minimum viable product",
  "Show clear, autonomous multi-step reasoning or task execution by the agent",
  "Address a genuine business challenge with a practical approach and usable outcome",
  "Be original work created during the hackathon period",
];

const CRITERIA = ["Innovation", "Feasibility", "Use of AWS/SAP Agentic AI", "Potential impact"];

const CONTACTS = [
  { name: "Ghina", phone: "081385623823" },
  { name: "Nabela", phone: "08212642669" },
  { name: "Aprisah", phone: "087881290760" },
  { name: "Nonny", phone: "087886675698" },
  { name: "Easter", phone: "0819-0818-974" },
];

const waLink = (phone: string) =>
  `https://wa.me/62${phone.replace(/\D/g, "").replace(/^0/, "")}`;

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-line">
      <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
          {eyebrow}
        </p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
          {title}
        </h2>
        <div className="mt-10">{children}</div>
      </div>
    </section>
  );
}

export default function Home() {
  return (
    <>
      <header className="sticky top-0 z-50 border-b border-line bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-4">
          <a href="#top" className="font-mono text-sm font-semibold tracking-widest">
            SOKRATES
          </a>
          <nav className="hidden gap-6 text-sm text-muted lg:flex">
            {NAV.map((item) => (
              <a key={item.href} href={item.href} className="hover:text-foreground">
                {item.label}
              </a>
            ))}
          </nav>
          <a
            href="#register"
            className="rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-90"
          >
            Register
          </a>
        </div>
      </header>

      <main id="top" className="flex-1">
        {/* Hero */}
        <div className="relative overflow-hidden">
          <div
            aria-hidden
            className="pointer-events-none absolute -top-40 left-1/2 h-[36rem] w-[64rem] -translate-x-1/2 rounded-full opacity-25 blur-3xl"
            style={{
              background:
                "radial-gradient(closest-side, var(--accent), var(--accent-2), transparent)",
            }}
          />
          <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-20 sm:pt-28">
            <p className="inline-flex items-center gap-2 rounded-full border border-line bg-card px-3 py-1 font-mono text-xs text-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              Universitas Bina Nusantara (BINUS) Alam Sutera
            </p>
            <h1 className="mt-6 max-w-4xl text-4xl font-semibold leading-[1.1] tracking-tight sm:text-6xl">
              AI Agentic Hackathon
              <span className="block bg-gradient-to-r from-accent to-accent-2 bg-clip-text text-transparent">
                Build the Future of Intelligent Innovation
              </span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
              A hands-on innovation program empowering the next generation of
              Indonesian developers, students, and technologists to turn ideas
              into real-world AI solutions with AWS and SAP Agentic AI.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <a
                href="#register"
                className="rounded-full bg-foreground px-6 py-3 font-medium text-background hover:opacity-90"
              >
                Submit your idea
              </a>
              <a
                href="#tracks"
                className="rounded-full border border-line px-6 py-3 font-medium text-foreground hover:border-muted"
              >
                Explore the tracks
              </a>
            </div>
            <dl className="mt-16 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-3">
              {[
                ["Prize pool", "IDR 130,000,000+"],
                ["Team size", "3 members"],
                ["Submission", "24 Aug – 10 Sep 2026"],
              ].map(([label, value]) => (
                <div key={label} className="bg-card px-6 py-6">
                  <dt className="font-mono text-xs uppercase tracking-[0.15em] text-muted">
                    {label}
                  </dt>
                  <dd className="mt-2 text-xl font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        {/* About */}
        <Section id="about" eyebrow="About" title="More than a competition">
          <div className="grid gap-10 md:grid-cols-2">
            <div className="space-y-5 text-lg leading-relaxed text-muted">
              <p>
                Hosted at Universitas Bina Nusantara (BINUS) Alam Sutera with
                SOKRATES as the host, the hackathon brings together university
                communities from across Indonesia to explore the power of AWS
                and SAP Agentic AI technologies through practical challenges,
                collaboration, and rapid innovation.
              </p>
              <p>
                This is a platform to learn, build, collaborate, and create
                impact. Participants receive hands-on enablement, develop
                practical AI skills, and gain exposure to technologies shaping
                the future of work and business.
              </p>
            </div>
            <div className="space-y-5 text-lg leading-relaxed text-muted">
              <p>
                The journey begins with online proposal submissions and
                qualification, followed by immersive enablement sessions, and
                culminates in an offline Demo Day, where the most promising
                solutions take center stage.
              </p>
              <p className="text-foreground">
                Together, we aim to inspire bold ideas, strengthen AI innovation
                in Indonesia, and build meaningful connections between talent,
                technology, universities, and industry.
              </p>
            </div>
          </div>
        </Section>

        {/* Tracks */}
        <Section id="tracks" eyebrow="Challenges" title="Two tracks. One mission.">
          <div className="grid gap-6 md:grid-cols-2">
            {TRACKS.map((track) => (
              <article
                key={track.n}
                className="rounded-2xl border border-line bg-card p-8 transition-colors hover:border-accent/50"
              >
                <span className="font-mono text-sm text-accent">{track.n}</span>
                <h3 className="mt-4 text-2xl font-semibold tracking-tight">
                  {track.title}
                </h3>
                <p className="mt-4 leading-relaxed text-muted">{track.body}</p>
              </article>
            ))}
          </div>
          <p className="mt-6 text-sm text-muted">
            Prizes are awarded separately for each challenge category.
          </p>
        </Section>

        {/* Who can join */}
        <Section id="join" eyebrow="Eligibility" title="Who can join?">
          <div className="grid gap-10 md:grid-cols-2">
            <div className="space-y-5 text-lg leading-relaxed text-muted">
              <p>
                The hackathon is open to university students and academic staff
                across Indonesia.
              </p>
              <p>
                Bring together the right mix of skills, ideas and perspectives.
                Students and academic staff can form a winning team and compete
                on equal footing.
              </p>
            </div>
            <div className="rounded-2xl border border-line bg-card p-8">
              <h3 className="text-xl font-semibold">Build your team of 3</h3>
              <p className="mt-4 leading-relaxed text-muted">
                Each team must consist of 3 members. Team members can be
                students, academic staff, or a combination of both — as long as
                all members are part of the university community.
              </p>
              <div className="mt-6 flex gap-3">
                {["01", "02", "03"].map((slot) => (
                  <div
                    key={slot}
                    className="flex h-16 flex-1 items-center justify-center rounded-xl border border-dashed border-line font-mono text-sm text-muted"
                  >
                    {slot}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Section>

        {/* Why join */}
        <Section id="why" eyebrow="Why join" title="Build. Learn. Get recognized.">
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {WHY.map((item) => (
              <article
                key={item.title}
                className="rounded-2xl border border-line bg-card p-7"
              >
                <span className="text-2xl">{item.icon}</span>
                <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
                <p className="mt-3 leading-relaxed text-muted">{item.body}</p>
              </article>
            ))}
          </div>
        </Section>

        {/* Prizes */}
        <Section id="prizes" eyebrow="Prizes" title="A prize pool of more than IDR 130,000,000">
          <div className="grid gap-6 md:grid-cols-3">
            {PRIZES.map((prize) => (
              <article
                key={prize.place}
                className={`rounded-2xl border p-8 ${
                  prize.featured
                    ? "border-gold/40 bg-gradient-to-b from-gold/10 to-card"
                    : "border-line bg-card"
                }`}
              >
                <p
                  className={`font-mono text-xs uppercase tracking-[0.15em] ${
                    prize.featured ? "text-gold" : "text-muted"
                  }`}
                >
                  {prize.place}
                </p>
                <p className="mt-4 text-3xl font-semibold tracking-tight">
                  {prize.amount}
                </p>
              </article>
            ))}
          </div>
          <p className="mt-6 text-sm text-muted">
            Prizes are awarded separately for each challenge category and are
            subject to a mandatory 5% government tax deduction.
          </p>
        </Section>

        {/* Register */}
        <Section id="register" eyebrow="Event agenda" title="From idea to Demo Day">
          <div className="grid gap-6 md:grid-cols-2">
            <article className="rounded-2xl border border-line bg-card p-8">
              <span className="font-mono text-sm text-accent">01</span>
              <h3 className="mt-4 text-2xl font-semibold tracking-tight">
                Create your winning team
              </h3>
              <p className="mt-4 leading-relaxed text-muted">
                Your team, your strategy. Build a team of 3 with the people you
                believe can take your idea all the way. Students, staff, or
                lecturers can join — as long as every team member belongs to the
                university community.
              </p>
            </article>

            <article className="rounded-2xl border border-line bg-card p-8">
              <span className="font-mono text-sm text-accent">02</span>
              <h3 className="mt-4 text-2xl font-semibold tracking-tight">
                Submit your idea
              </h3>
              <p className="mt-3 font-mono text-sm text-gold">
                24 August – 10 September 2026
              </p>
              <p className="mt-4 leading-relaxed text-muted">
                Submit a maximum 3-page proposal describing your problem
                statement, proposed Agentic AI solution, and expected impact.
              </p>
            </article>
          </div>

          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <article className="rounded-2xl border border-line bg-card p-8">
              <h3 className="text-lg font-semibold">All submissions should</h3>
              <ul className="mt-5 space-y-4">
                {SUBMISSION_RULES.map((rule) => (
                  <li key={rule} className="flex gap-3 leading-relaxed text-muted">
                    <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    {rule}
                  </li>
                ))}
              </ul>
            </article>

            <article className="rounded-2xl border border-line bg-card p-8">
              <h3 className="text-lg font-semibold">Judging criteria</h3>
              <ul className="mt-5 space-y-3">
                {CRITERIA.map((item, i) => (
                  <li
                    key={item}
                    className="flex items-center gap-4 rounded-xl border border-line px-5 py-4"
                  >
                    <span className="font-mono text-sm text-muted">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="font-medium">{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          </div>
        </Section>

        {/* Contact */}
        <Section
          id="contact"
          eyebrow="Contact"
          title="Informasi kegiatan & pendaftaran"
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CONTACTS.map((person) => (
              <a
                key={person.name}
                href={waLink(person.phone)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between gap-4 rounded-2xl border border-line bg-card px-6 py-5 transition-colors hover:border-accent/50"
              >
                <span>
                  <span className="block font-medium">{person.name}</span>
                  <span className="block font-mono text-sm text-muted">
                    {person.phone}
                  </span>
                </span>
                <span aria-hidden className="text-muted">
                  →
                </span>
              </a>
            ))}
          </div>
        </Section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-10 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
          <p>AI Agentic Hackathon — hosted by SOKRATES at BINUS Alam Sutera.</p>
          <p>Powered by AWS &amp; SAP Agentic AI.</p>
        </div>
      </footer>
    </>
  );
}
