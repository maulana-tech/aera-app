import type { DesignSystem, Page, SlideMeta } from '@open-slide/core';
import { useSlidePageNumber } from '@open-slide/core';
import type { CSSProperties, ReactNode } from 'react';

import architecture from './assets/architecture.svg';

export const design: DesignSystem = {
  palette: { bg: '#0B0D10', text: '#F5F6F7', accent: '#E5484D' },
  fonts: {
    display: '-apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif',
    body: '-apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif',
  },
  typeScale: { hero: 150, body: 36 },
  radius: 14,
};

const ink = {
  soft: '#C3C8CF',
  muted: '#8A919B',
  dim: '#596069',
  rule: '#1F242C',
  panel: '#12161D',
  red: '#E5484D',
  redSoft: 'rgba(229, 72, 77, 0.13)',
  green: '#3DD68C',
  greenSoft: 'rgba(61, 214, 140, 0.12)',
  amber: '#F5A524',
  amberSoft: 'rgba(245, 165, 36, 0.13)',
  blue: '#6E97F0',
};

const mono = '"SF Mono", ui-monospace, Menlo, Consolas, monospace';

const fill: CSSProperties = {
  width: '100%',
  height: '100%',
  background: 'var(--osd-bg)',
  color: 'var(--osd-text)',
  fontFamily: 'var(--osd-font-body)',
  position: 'relative',
};

const Footer = ({ label }: { label: string }) => {
  const { current, total } = useSlidePageNumber();
  return (
    <div
      style={{
        position: 'absolute',
        left: 120,
        right: 120,
        bottom: 56,
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 22,
        color: ink.dim,
        letterSpacing: '0.04em',
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
  <div
    style={{
      fontSize: 24,
      letterSpacing: '0.22em',
      textTransform: 'uppercase',
      color: 'var(--osd-accent)',
      fontWeight: 600,
    }}
  >
    {children}
  </div>
);

const Frame = ({
  eyebrow,
  heading,
  footer,
  children,
}: {
  eyebrow: string;
  heading: string;
  footer: string;
  children: ReactNode;
}) => (
  <div style={{ ...fill, padding: '110px 120px 0' }}>
    <Eyebrow>{eyebrow}</Eyebrow>
    <h2
      style={{
        fontFamily: 'var(--osd-font-display)',
        fontSize: 68,
        lineHeight: 1.15,
        fontWeight: 800,
        margin: '26px 0 0',
        letterSpacing: '-0.02em',
      }}
    >
      {heading}
    </h2>
    <div style={{ marginTop: 52 }}>{children}</div>
    <Footer label={footer} />
  </div>
);

const Divider = ({ n, title, lead }: { n: string; title: string; lead: string }) => (
  <div
    style={{
      ...fill,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      padding: '0 140px',
    }}
  >
    <div style={{ fontFamily: mono, fontSize: 30, color: 'var(--osd-accent)' }}>{n}</div>
    <h2
      style={{
        fontFamily: 'var(--osd-font-display)',
        fontSize: 108,
        fontWeight: 850,
        margin: '28px 0 0',
        letterSpacing: '-0.03em',
        lineHeight: 1.08,
      }}
    >
      {title}
    </h2>
    <p style={{ fontSize: 38, color: ink.muted, margin: '36px 0 0', maxWidth: 1180, lineHeight: 1.5 }}>
      {lead}
    </p>
  </div>
);

const Claim = ({ children }: { children: ReactNode }) => (
  <p
    style={{
      fontSize: 44,
      lineHeight: 1.45,
      color: 'var(--osd-text)',
      margin: 0,
      maxWidth: 1480,
      fontWeight: 600,
    }}
  >
    {children}
  </p>
);

const Bullet = ({ children }: { children: ReactNode }) => (
  <li style={{ fontSize: 'var(--osd-size-body)', lineHeight: 1.45, marginBottom: 26, color: ink.soft }}>
    {children}
  </li>
);

const Chip = ({ tone, children }: { tone: 'red' | 'green' | 'amber'; children: ReactNode }) => {
  const look =
    tone === 'red'
      ? { bg: ink.redSoft, fg: ink.red }
      : tone === 'green'
        ? { bg: ink.greenSoft, fg: ink.green }
        : { bg: ink.amberSoft, fg: ink.amber };
  return (
    <span
      style={{
        background: look.bg,
        color: look.fg,
        fontFamily: mono,
        fontSize: 24,
        padding: '8px 18px',
        borderRadius: 999,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
};

const Cover: Page = () => (
  <div style={{ ...fill, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '0 140px' }}>
    <Eyebrow>SAP + AWS Hackathon Indonesia 2026 · Supply Chain</Eyebrow>
    <h1
      style={{
        fontFamily: 'var(--osd-font-display)',
        fontSize: 'var(--osd-size-hero)',
        fontWeight: 900,
        letterSpacing: '-0.04em',
        margin: '34px 0 0',
        lineHeight: 1,
      }}
    >
      SIGAP
    </h1>
    <p style={{ fontSize: 42, color: ink.soft, margin: '30px 0 0', maxWidth: 1380, lineHeight: 1.4 }}>
      Supply Disruption Intelligence &amp; Anticipation — asisten multi-agen otonom untuk
      manufaktur Indonesia.
    </p>
    <div style={{ height: 1, background: ink.rule, margin: '56px 0 0', width: 980 }} />
    <p style={{ fontSize: 34, color: ink.muted, margin: '40px 0 0', maxWidth: 1320, lineHeight: 1.45 }}>
      Mengubah gangguan pasokan dari investigasi berhari-hari menjadi satu rekomendasi
      siap-tanda-tangan dalam hitungan menit —{' '}
      <span style={{ color: 'var(--osd-text)', fontWeight: 600 }}>
        tanpa membiarkan AI mengarang angka atau melanggar aturan.
      </span>
    </p>
  </div>
);

const SectionProblem: Page = () => (
  <Divider
    n="01"
    title="Masalahnya bukan kecepatan saja"
    lead="Datanya sudah ada di S/4HANA. Yang hilang adalah jam-jam antara sinyal dan keputusan — dan satu dimensi yang khas Indonesia."
  />
);

const ProblemClaim: Page = () => (
  <Frame eyebrow="Masalah" heading="Saat pasokan terputus, keputusan tercepat sering yang paling tidak boleh diambil." footer="Masalah">
    <ul style={{ margin: '14px 0 0', paddingLeft: 42, listStyle: 'none' }}>
      <Bullet>Topan menutup satu pelabuhan — puluhan material berhenti</Bullet>
      <Bullet>Planner punya jam, bukan hari, untuk memutuskan</Bullet>
      <Bullet>
        Opsi termurah sering{' '}
        <span style={{ color: 'var(--osd-text)', fontWeight: 600 }}>melanggar TKDN atau tertahan LARTAS</span>
      </Bullet>
      <Bullet>Setelahnya: tak ada catatan siapa memutuskan apa, atas dasar apa</Bullet>
    </ul>
  </Frame>
);

const Beat = ({
  n,
  title,
  body,
  tone,
}: {
  n: string;
  title: string;
  body: string;
  tone: 'normal' | 'bad';
}) => (
  <div style={{ flex: 1 }}>
    <div style={{ height: 3, background: tone === 'bad' ? ink.red : ink.rule }} />
    <div style={{ fontFamily: mono, fontSize: 22, color: tone === 'bad' ? ink.red : ink.dim, marginTop: 24 }}>
      {n}
    </div>
    <div style={{ fontSize: 34, fontWeight: 700, marginTop: 16, lineHeight: 1.25 }}>{title}</div>
    <div style={{ fontSize: 26, color: ink.muted, marginTop: 14, lineHeight: 1.45 }}>{body}</div>
  </div>
);

const ProblemTimeline: Page = () => (
  <Frame eyebrow="Masalah" heading="Hari ini, jalurnya begini" footer="Masalah">
    <div style={{ display: 'flex', gap: 48, marginTop: 30 }}>
      <Beat n="JAM 0" title="Sinyal masuk" body="Berita, grup WhatsApp, telepon dari forwarder." tone="normal" />
      <Beat n="HARI 1–3" title="Menelusuri manual" body="Excel, email, tanya satu-satu: order mana yang kena." tone="normal" />
      <Beat n="HARI 3" title="Keputusan" body="Diambil dari data yang sudah basi sejak Selasa." tone="normal" />
      <Beat n="SETELAHNYA" title="Tak ada jejak" body="Tak ada catatan dasar keputusan. Audit jadi rekonstruksi." tone="bad" />
    </div>
    <p style={{ fontSize: 32, color: ink.soft, marginTop: 72, maxWidth: 1500, lineHeight: 1.5 }}>
      Mempercepat keputusan saja justru berbahaya: yang dipercepat bisa keputusan yang melanggar kontrak.
    </p>
  </Frame>
);

const RuleCard = ({
  tag,
  title,
  body,
}: {
  tag: string;
  title: string;
  body: string;
}) => (
  <div
    style={{
      flex: 1,
      background: ink.panel,
      border: `1px solid ${ink.rule}`,
      borderRadius: 'var(--osd-radius)',
      padding: 44,
    }}
  >
    <div style={{ fontFamily: mono, fontSize: 24, color: 'var(--osd-accent)' }}>{tag}</div>
    <div style={{ fontSize: 40, fontWeight: 750, marginTop: 20, lineHeight: 1.2 }}>{title}</div>
    <div style={{ fontSize: 28, color: ink.soft, marginTop: 20, lineHeight: 1.5 }}>{body}</div>
  </div>
);

const ProblemIndonesia: Page = () => (
  <Frame eyebrow="Masalah" heading="Dua aturan yang membuat opsi termurah jadi terlarang" footer="Masalah">
    <div style={{ display: 'flex', gap: 48, marginTop: 24 }}>
      <RuleCard
        tag="TKDN"
        title="Tingkat Komponen Dalam Negeri"
        body="Kontrak OEM mewajibkan lantai konten lokal. Impor menggerusnya — dan perusahaan yang sudah di bawah lantai tak boleh memperburuk posisinya."
      />
      <RuleCard
        tag="LARTAS"
        title="Larangan &amp; Pembatasan impor"
        body="Asal impor baru butuh izin. Itu bukan biaya, itu hari kerja — dan hari kerja menggeser tanggal tiba, bukan harga."
      />
    </div>
    <p style={{ fontSize: 32, color: ink.soft, marginTop: 64, maxWidth: 1520, lineHeight: 1.5 }}>
      Keduanya tak ada di dashboard supply chain mana pun. Keduanya yang menentukan apakah
      sebuah opsi benar-benar boleh diambil.
    </p>
  </Frame>
);

const SectionSolution: Page = () => (
  <Divider
    n="02"
    title="Dua belas agen, satu keputusan yang bisa disetujui"
    lead="Dari sinyal publik sampai dokumen SAP, otonom — tapi berhenti di tempat yang benar."
  />
);

const StepCell = ({ n, title, body }: { n: string; title: string; body: string }) => (
  <div>
    <div style={{ fontFamily: mono, fontSize: 24, color: 'var(--osd-accent)' }}>{n}</div>
    <div style={{ fontSize: 38, fontWeight: 750, marginTop: 14, lineHeight: 1.2 }}>{title}</div>
    <div style={{ fontSize: 27, color: ink.muted, marginTop: 14, lineHeight: 1.45 }}>{body}</div>
  </div>
);

const SixSteps: Page = () => (
  <Frame eyebrow="Solusi" heading="Enam langkah, tanpa seorang pun memulainya" footer="Solusi">
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        columnGap: 110,
        rowGap: 48,
        marginTop: 18,
      }}
    >
      <StepCell n="01 MENANGKAP" title="Watcher, bukan inbox" body="BMKG, GDACS, NASA EONET, USGS, Open-Meteo — tanpa diminta." />
      <StepCell n="02 MENELUSURI" title="Dua belas agen membaca" body="S/4HANA, master data, upload, feed publik." />
      <StepCell n="03 MENYARING" title="Kira mencoret yang melanggar" body="TKDN dan LARTAS, sebelum harga ikut bicara." />
      <StepCell n="04 MENGHITUNG" title="Tara memberi angka" body="Biaya, tanggal habis stok, OTIF, dampak TKDN." />
      <StepCell n="05 MENGEKSEKUSI" title="Masuk ke SAP" body="Stock transfer atau draft PO, dalam batas wewenang." />
      <StepCell n="06 MENUTUP" title="Hasil nyata dicatat" body="Insiden berikutnya bisa mencarinya sebagai preseden." />
    </div>
  </Frame>
);

const AgentCell = ({
  nick,
  role,
  veto,
}: {
  nick: string;
  role: string;
  veto?: boolean;
}) => (
  <div
    style={{
      background: veto ? ink.redSoft : ink.panel,
      border: `1px solid ${veto ? ink.red : ink.rule}`,
      borderRadius: 'var(--osd-radius)',
      padding: '26px 28px',
    }}
  >
    <div style={{ fontSize: 34, fontWeight: 800, color: veto ? ink.red : 'var(--osd-text)' }}>{nick}</div>
    <div style={{ fontSize: 24, color: veto ? ink.red : ink.muted, marginTop: 10, lineHeight: 1.3 }}>{role}</div>
  </div>
);

const TheTeam: Page = () => (
  <Frame eyebrow="Solusi" heading="Satu agen punya hak veto — dan veto itu bukan prompt" footer="Solusi">
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 28,
        marginTop: 10,
      }}
    >
      <AgentCell nick="Arya" role="Team lead" />
      <AgentCell nick="Elsa" role="Dampak" />
      <AgentCell nick="Dara" role="Permintaan" />
      <AgentCell nick="Iris" role="Validitas stok" />
      <AgentCell nick="Clint" role="Sourcing" />
      <AgentCell nick="Prita" role="Pengadaan" />
      <AgentCell nick="Milo" role="Logistik" />
      <AgentCell nick="Kira" role="Aturan · VETO" veto />
      <AgentCell nick="Tara" role="Costing" />
      <AgentCell nick="Otto" role="Preseden" />
      <AgentCell nick="Bram" role="Eksekusi" />
      <AgentCell nick="Vega" role="Pemindai risiko" />
    </div>
    <p style={{ fontSize: 30, color: ink.soft, marginTop: 52, maxWidth: 1540, lineHeight: 1.5 }}>
      Yang membedakan bukan jumlahnya. Veto Kira ada di Python, dan{' '}
      <span style={{ color: 'var(--osd-text)', fontWeight: 600 }}>tidak bisa dibatalkan dengan alasan biaya.</span>
    </p>
  </Frame>
);

const DoorCard = ({
  n,
  where,
  what,
  detail,
}: {
  n: string;
  where: string;
  what: string;
  detail: string;
}) => (
  <div
    style={{
      flex: 1,
      background: ink.panel,
      border: `1px solid ${ink.rule}`,
      borderRadius: 'var(--osd-radius)',
      padding: 44,
    }}
  >
    <div style={{ fontFamily: mono, fontSize: 24, color: 'var(--osd-accent)' }}>{n}</div>
    <div style={{ fontSize: 36, fontWeight: 750, marginTop: 18, lineHeight: 1.22 }}>{where}</div>
    <div style={{ fontSize: 28, color: ink.soft, marginTop: 20, lineHeight: 1.5 }}>{what}</div>
    <div style={{ height: 1, background: ink.rule, margin: '28px 0' }} />
    <div style={{ fontSize: 25, color: ink.muted, lineHeight: 1.45 }}>{detail}</div>
  </div>
);

const TwoDoors: Page = () => (
  <Frame eyebrow="Solusi" heading="Veto di dua pintu, bukan satu" footer="Solusi">
    <div style={{ display: 'flex', gap: 44, marginTop: 16 }}>
      <DoorCard
        n="PINTU 1"
        where="Saat opsi dipilih"
        what="Setiap sumber alternatif dinilai terhadap lantai TKDN dan LARTAS sebelum biaya dibandingkan."
        detail="Opsi E — Rp 48 jt, termurah — dicoret: TKDN jatuh ke 34,8%."
      />
      <DoorCard
        n="PINTU 2"
        where="Saat PO diterbitkan"
        what="Supplier-nya sendiri dinilai. PO ke supplier yang diblok ditolak, bukan diberi peringatan."
        detail="Dari 18 supplier: 6 domestik lolos, 12 asing diblok."
      />
    </div>
    <p style={{ fontSize: 30, color: ink.soft, marginTop: 56, maxWidth: 1560, lineHeight: 1.5 }}>
      Tanpa pintu kedua, jalur pengadaan bisa sampai ke draft PO tanpa pernah dinilai —
      harga lewat pintu belakang.
    </p>
  </Frame>
);

const SectionArchitecture: Page = () => (
  <Divider
    n="03"
    title="AWS untuk otaknya, SAP untuk datanya dan pintunya"
    lead="Dan jaminannya ada di kode, bukan di prompt."
  />
);

const StackRow = ({ name, body }: { name: string; body: string }) => (
  <div style={{ marginBottom: 32 }}>
    <div style={{ fontSize: 31, fontWeight: 700, lineHeight: 1.25 }}>{name}</div>
    <div style={{ fontSize: 25, color: ink.muted, marginTop: 10, lineHeight: 1.45 }}>{body}</div>
  </div>
);

const StackColumn = ({
  title,
  tone,
  children,
}: {
  title: string;
  tone: string;
  children: ReactNode;
}) => (
  <div style={{ flex: 1 }}>
    <div style={{ height: 3, background: tone }} />
    <div style={{ fontSize: 40, fontWeight: 850, marginTop: 24, marginBottom: 34, letterSpacing: '-0.01em' }}>
      {title}
    </div>
    {children}
  </div>
);

const TechStack: Page = () => (
  <Frame eyebrow="Arsitektur" heading="Dua provider model, dengan sengaja" footer="Arsitektur">
    <div style={{ display: 'flex', gap: 110, marginTop: 10 }}>
      <StackColumn title="AWS" tone={ink.amber}>
        <StackRow name="Amazon Bedrock" body="Claude untuk pengambil keputusan; MiniMax, DeepSeek, Kimi untuk spesialis." />
        <StackRow name="AgentCore Gateway" body="Seluruh tool kami diekspos sebagai MCP." />
        <StackRow name="EC2 · satu proses Python" body="Tanpa orkestrator, tanpa message broker." />
      </StackColumn>
      <StackColumn title="SAP" tone={ink.blue}>
        <StackRow name="S/4HANA Cloud" body="Stok, BOM, purchase order, sales order, supplier." />
        <StackRow name="SAP AI Core" body="gpt-5.4, dan sap-rpt-1.6 untuk prediksi tabular." />
        <StackRow name="Joule · A2A" body="Tiga skill read-only. BTP Cloud Foundry untuk cf push." />
      </StackColumn>
    </div>
    <p style={{ fontSize: 29, color: ink.soft, marginTop: 30, maxWidth: 1600, lineHeight: 1.5 }}>
      Pengambil keputusan jalan di model terkuat, sepuluh spesialis boleh jalan di model murah —{' '}
      <span style={{ color: 'var(--osd-text)', fontWeight: 600 }}>dan tak satu pun jaminan melemah.</span>
    </p>
  </Frame>
);

const ArchitectureDiagram: Page = () => (
  <div style={{ ...fill, padding: '72px 72px 104px', display: 'flex', flexDirection: 'column' }}>
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 28, marginBottom: 26 }}>
      <div style={{ fontSize: 34, fontWeight: 800 }}>Satu proses, dua cloud</div>
      <div style={{ fontSize: 24, color: ink.muted }}>
        sigap/architecture/diagram.py — digenerate, bukan digambar tangan
      </div>
    </div>
    <div
      style={{
        flex: 1,
        background: '#FFFFFF',
        borderRadius: 'var(--osd-radius)',
        padding: 28,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 0,
      }}
    >
      <img
        src={architecture}
        alt="Arsitektur SIGAP di AWS dan SAP"
        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
      />
    </div>
  </div>
);

const StdlibOnly: Page = () => (
  <Frame eyebrow="Arsitektur" heading="Agent service: Python 3, standard library saja" footer="Arsitektur">
    <Claim>
      <span style={{ fontFamily: mono, color: ink.green }}>http.server</span> +{' '}
      <span style={{ fontFamily: mono, color: ink.green }}>sqlite3</span>. xlsx dan PDF ditulis
      sendiri. Satu paket terpasang, dan hanya kalau Bedrock dipakai.
    </Claim>
    <ul style={{ margin: '56px 0 0', paddingLeft: 42, listStyle: 'none' }}>
      <Bullet>Bisa dibaca ujung ke ujung — tak ada framework yang menyembunyikan jalurnya</Bullet>
      <Bullet>Jalan di mesin apa pun yang punya Python, termasuk EC2 kosong</Bullet>
      <Bullet>Tak ada dependensi yang bisa pensiun di tengah kompetisi</Bullet>
    </ul>
  </Frame>
);

const DemoDivider: Page = () => (
  <div
    style={{
      ...fill,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
    }}
  >
    <div style={{ fontFamily: mono, fontSize: 30, color: 'var(--osd-accent)', letterSpacing: '0.24em' }}>
      LIVE
    </div>
    <h2
      style={{
        fontFamily: 'var(--osd-font-display)',
        fontSize: 132,
        fontWeight: 900,
        margin: '32px 0 0',
        letterSpacing: '-0.03em',
      }}
    >
      Demo
    </h2>
    <p style={{ fontSize: 34, color: ink.muted, margin: '36px 0 0', textAlign: 'center', maxWidth: 1180, lineHeight: 1.5 }}>
      Topan menutup Port of Ningbo enam hari. Material M-4471.
      <br />
      PT Karya Presisi Nusantara.
    </p>
  </div>
);

const SectionTrust: Page = () => (
  <Divider
    n="04"
    title="Kenapa angkanya bisa dipercaya"
    lead="Agen lain menjawab dengan percaya diri. Yang ini menolak menjawab kalau datanya tak layak."
  />
);

const OriginRow = ({
  tag,
  meaning,
  trusted,
}: {
  tag: string;
  meaning: string;
  trusted: boolean;
}) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 36, marginBottom: 26 }}>
    <div
      style={{
        fontFamily: mono,
        fontSize: 28,
        color: trusted ? ink.green : ink.amber,
        width: 220,
        flexShrink: 0,
      }}
    >
      {tag}
    </div>
    <div style={{ fontSize: 29, color: ink.soft, lineHeight: 1.4 }}>{meaning}</div>
  </div>
);

const Provenance: Page = () => (
  <Frame eyebrow="Kepercayaan" heading="Setiap fakta membawa label asalnya" footer="Kepercayaan">
    <div style={{ marginTop: 8 }}>
      <OriginRow tag="live" meaning="Langsung dari S/4HANA atau API resmi" trusted />
      <OriginRow tag="cached" meaning="Pernah live, membawa waktu fetch sebenarnya" trusted />
      <OriginRow tag="derived" meaning="Dihitung dari sesuatu yang live" trusted />
      <OriginRow tag="modelled" meaning="Profil perusahaan atau fixture — diakui terbuka" trusted={false} />
      <OriginRow tag="missing" meaning="Sistem berhenti di sini, bukan menebak" trusted={false} />
    </div>
    <p style={{ fontSize: 30, color: ink.soft, marginTop: 34, maxWidth: 1560, lineHeight: 1.5 }}>
      Gagal fetch menjadi <span style={{ fontFamily: mono, color: ink.amber }}>missing</span> — bukan
      tebakan yang kelihatan meyakinkan. Dan sebuah temuan tak pernah lebih tepercaya dari bahan
      terlemahnya.
    </p>
  </Frame>
);

const CalculatorRefuses: Page = () => (
  <Frame eyebrow="Kepercayaan" heading="Kalkulatornya tanpa model — dan ia menolak" footer="Kepercayaan">
    <Claim>
      Kalau satu input tidak tepercaya, kalkulatornya{' '}
      <span style={{ color: ink.red }}>menolak mengeluarkan angka rupiah</span> — bukan menebak.
    </Claim>
    <div
      style={{
        marginTop: 54,
        background: ink.panel,
        border: `1px solid ${ink.rule}`,
        borderRadius: 'var(--osd-radius)',
        padding: '38px 44px',
        fontFamily: mono,
        fontSize: 29,
        color: ink.amber,
        maxWidth: 1500,
      }}
    >
      &quot;No savings figure until that data is live.&quot;
    </div>
    <ul style={{ margin: '50px 0 0', paddingLeft: 42, listStyle: 'none' }}>
      <Bullet>Daftar aturan dari model hanya boleh mempersempit, tak pernah melonggarkan</Bullet>
      <Bullet>Identitas diambil dari token, tak pernah dari body permintaan</Bullet>
    </ul>
  </Frame>
);

const PlanRow = ({
  label,
  plan,
  figure,
  tone,
  strike,
}: {
  label: string;
  plan: string;
  figure: string;
  tone: 'green' | 'red' | 'accent';
  strike?: boolean;
}) => {
  const fg = tone === 'green' ? ink.green : tone === 'red' ? ink.red : 'var(--osd-text)';
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 40,
        padding: '30px 0',
        borderBottom: `1px solid ${ink.rule}`,
      }}
    >
      <div style={{ fontFamily: mono, fontSize: 24, color: ink.dim, width: 300, flexShrink: 0 }}>
        {label}
      </div>
      <div style={{ fontSize: 32, color: ink.soft, flex: 1 }}>{plan}</div>
      <div
        style={{
          fontSize: 44,
          fontWeight: 800,
          color: fg,
          fontVariantNumeric: 'tabular-nums',
          textDecoration: strike ? 'line-through' : 'none',
          whiteSpace: 'nowrap',
        }}
      >
        {figure}
      </div>
    </div>
  );
};

const PriceOfRules: Page = () => (
  <Frame eyebrow="Kepercayaan · halaman terpenting" heading="Kepatuhan punya harga, dan harganya ada di catatan" footer="Kepercayaan">
    <div style={{ marginTop: 4 }}>
      <PlanRow label="DIPILIH" plan="B + C — Gresik + transfer internal · TKDN 41,6%" figure="Rp 116.000.000" tone="green" />
      <PlanRow label="LEBIH MURAH, DICORET" plan="C + E — transfer internal + China · TKDN 34,8%" figure="Rp 70.000.000" tone="red" strike />
      <PlanRow label="HARGA ATURANNYA" plan="Selisih yang dibayar untuk tetap patuh" figure="Rp 46.000.000" tone="accent" />
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginTop: 42, flexWrap: 'wrap' }}>
      <Chip tone="red">E — TKDN drops to 34.8%, contract floor 40%</Chip>
      <Chip tone="amber">modelled</Chip>
      <span style={{ fontSize: 25, color: ink.muted }}>
        rule pack demo belum terverifikasi — dan sistemnya mengatakannya sendiri
      </span>
    </div>
  </Frame>
);

const AuthorityLimits: Page = () => (
  <Frame eyebrow="Kepercayaan" heading="Model mengusulkan. Ia tidak pernah memutuskan, tidak pernah membelanjakan." footer="Kepercayaan">
    <div style={{ display: 'flex', gap: 44, marginTop: 14 }}>
      <RuleCard
        tag="OTONOM"
        title="Di bawah batas"
        body="Transfer stok kecil yang aman boleh jalan sendiri. Biaya yang dikecilkan oleh model mencabut otonominya — bukan aksinya."
      />
      <RuleCard
        tag="BERHENTI"
        title="Di atas batas"
        body="Sistem berhenti dan menunggu orang. Limit diperiksa di server sesuai peran: buyer sampai Rp 500 juta."
      />
    </div>
    <p style={{ fontSize: 30, color: ink.soft, marginTop: 56, maxWidth: 1560, lineHeight: 1.5 }}>
      Approve dua kali tidak mengirim dua kali. Aksi ke SAP memakai idempotency key, dan setiap
      langkah mendarat di log keputusan.
    </p>
  </Frame>
);

const ClosedLoop: Page = () => (
  <Frame eyebrow="Kepercayaan" heading="Prediksi tanpa hasil cuma pendapat" footer="Kepercayaan">
    <Claim>
      Hasil nyata setiap aksi dicatat sekali — lalu laporan menampilkan{' '}
      <span style={{ color: ink.green }}>prediksi vs realisasi beserta selisihnya.</span>
    </Claim>
    <ul style={{ margin: '54px 0 0', paddingLeft: 42, listStyle: 'none' }}>
      <Bullet>Insiden itu menjadi preseden yang dicari pada kejadian berikutnya</Bullet>
      <Bullet>Biaya aktual tak diisi? Laporannya menulis &quot;—&quot;, bukan menebak angka</Bullet>
      <Bullet>
        Hasil masa lalu <span style={{ color: 'var(--osd-text)', fontWeight: 600 }}>belum</span>{' '}
        menggeser ranking — itu urutan terakhir, sengaja
      </Bullet>
    </ul>
  </Frame>
);

const WatcherRow = ({ name, cadence, body }: { name: string; cadence: string; body: string }) => (
  <div style={{ display: 'flex', alignItems: 'baseline', gap: 32, marginBottom: 24 }}>
    <div style={{ fontFamily: mono, fontSize: 27, color: 'var(--osd-accent)', width: 230, flexShrink: 0 }}>
      {name}
    </div>
    <div style={{ fontFamily: mono, fontSize: 23, color: ink.dim, width: 150, flexShrink: 0 }}>{cadence}</div>
    <div style={{ fontSize: 28, color: ink.soft, lineHeight: 1.4 }}>{body}</div>
  </div>
);

const Watchers: Page = () => (
  <Frame eyebrow="Kepercayaan" heading="Lima watcher — satu di antaranya tak punya feed" footer="Kepercayaan">
    <div style={{ marginTop: 6 }}>
      <WatcherRow name="bmkg" cadence="5 menit" body="Gempa M5.0+ dalam 300 km dari fasilitas" />
      <WatcherRow name="hazards" cadence="30 menit" body="Topan, banjir, gempa, erupsi (GDACS, EONET, USGS)" />
      <WatcherRow name="weather" cadence="3 jam" body="Angin kencang, gelombang tinggi, hujan ekstrem" />
      <WatcherRow name="exposure" cadence="mingguan" body="Risiko yang belum terjadi — single source, cover tipis" />
      <WatcherRow name="certificates" cadence="harian" body="Sertifikat TKDN yang habis dalam 60 hari" />
    </div>
    <p style={{ fontSize: 29, color: ink.soft, marginTop: 36, maxWidth: 1600, lineHeight: 1.5 }}>
      Yang terakhir tak bisa dilihat feed mana pun: kedaluwarsanya ada di arsip perusahaan sendiri,
      dan konten lokal di belakangnya ikut hilang saat ia lewat.
    </p>
  </Frame>
);

const Metric = ({ figure, label }: { figure: string; label: string }) => (
  <div style={{ flex: 1 }}>
    <div
      style={{
        fontSize: 84,
        fontWeight: 850,
        letterSpacing: '-0.03em',
        fontVariantNumeric: 'tabular-nums',
        lineHeight: 1,
      }}
    >
      {figure}
    </div>
    <div style={{ fontSize: 25, color: ink.muted, marginTop: 18, lineHeight: 1.35 }}>{label}</div>
  </div>
);

const SelfChecked: Page = () => (
  <Frame eyebrow="Kepercayaan" heading="Setiap modul menguji dirinya sendiri" footer="Kepercayaan">
    <div style={{ display: 'flex', gap: 36, marginTop: 20 }}>
      <Metric figure="56" label="modul dengan self-check, nol gagal" />
      <Metric figure="46" label="tool, semuanya terpasang" />
      <Metric figure="12" label="agen, 12 prompt tertulis" />
      <Metric figure="8" label="job terjadwal, 5 watcher" />
    </div>
    <div
      style={{
        marginTop: 62,
        background: ink.panel,
        border: `1px solid ${ink.rule}`,
        borderRadius: 'var(--osd-radius)',
        padding: '32px 44px',
        fontFamily: mono,
        fontSize: 27,
        color: ink.green,
        maxWidth: 1560,
      }}
    >
      $ python3 manage.py check <span style={{ color: ink.dim }}>→</span> 56 ok · FAILED: none
    </div>
    <p style={{ fontSize: 28, color: ink.muted, marginTop: 34, maxWidth: 1580, lineHeight: 1.5 }}>
      Kalau juri bertanya &quot;ini jalan, atau cuma demo?&quot; — jawabannya satu perintah, 40 detik.
    </p>
  </Frame>
);

const SectionImpact: Page = () => (
  <Divider
    n="05"
    title="Dampak, keadaan jujur, dan jalan ke produksi"
    lead="Sudah jalan hari ini, dan kami tahu persis apa yang belum."
  />
);

const Impact: Page = () => (
  <Frame eyebrow="Dampak" heading="Pada skenario Ningbo" footer="Dampak">
    <div style={{ display: 'flex', gap: 36, marginTop: 16 }}>
      <Metric figure="hari → menit" label="penelusuran dampak sampai rekomendasi" />
      <Metric figure="38%" label="lebih murah dari refleks air freight (Rp 186 jt → Rp 116 jt)" />
      <Metric figure="Rp 46 jt" label="harga kepatuhan, tercatat — bukan perasaan" />
    </div>
    <ul style={{ margin: '66px 0 0', paddingLeft: 42, listStyle: 'none' }}>
      <Bullet>Opsi tak patuh tersaring di dua pintu, sebelum menjadi dokumen SAP</Bullet>
      <Bullet>Jejak audit per keputusan: siapa, kapan, atas bukti apa, dengan label asalnya</Bullet>
    </ul>
  </Frame>
);

const HonestState: Page = () => (
  <Frame eyebrow="Keadaan jujur" heading="Yang belum — dan kami katakan di slide ini" footer="Keadaan jujur">
    <ul style={{ margin: '10px 0 0', paddingLeft: 42, listStyle: 'none' }}>
      <Bullet>
        Rule pack masih <span style={{ fontFamily: mono, color: ink.amber }}>verified:false</span> —
        tiap ruling dilabeli <span style={{ fontFamily: mono, color: ink.amber }}>modelled</span>
      </Bullet>
      <Bullet>SQLite di Cloud Foundry hilang saat restart — Postgres dulu</Bullet>
      <Bullet>Jalur tulis SAP belum diuji di tenant pelanggan</Bullet>
      <Bullet>Mailbox alert belum tersambung — notifikasi berhenti di antrean</Bullet>
      <Bullet>Hasil nyata dicatat dan ditampilkan, belum mempengaruhi ranking</Bullet>
    </ul>
    <p style={{ fontSize: 29, color: ink.soft, marginTop: 44, maxWidth: 1600, lineHeight: 1.5 }}>
      Halaman ini ada karena produk yang menolak mengarang angka tak boleh mengarang kesiapannya.
    </p>
  </Frame>
);

const Roadmap: Page = () => (
  <Frame eyebrow="Jalan ke produksi" heading="Berurutan, bukan daftar keinginan" footer="Roadmap">
    <div style={{ display: 'flex', gap: 40, marginTop: 20 }}>
      <Beat n="LANGKAH 1" title="Postgres" body="Catatan keputusan tak boleh hilang saat restart." tone="normal" />
      <Beat n="LANGKAH 2" title="Rule pack diverifikasi" body="Angka kontrak asli, diperiksa orang bersama tim pengadaan." tone="normal" />
      <Beat n="LANGKAH 3" title="Tulis ke SAP diuji" body="Di tenant sungguhan, bukan sandbox." tone="normal" />
      <Beat n="BARU SETELAHNYA" title="Belajar dari hasil" body="Realisasi boleh mempengaruhi ranking." tone="bad" />
    </div>
    <p style={{ fontSize: 31, color: ink.soft, marginTop: 72, maxWidth: 1600, lineHeight: 1.5 }}>
      Yang terakhir kami taruh paling belakang dengan sengaja: membiarkan sistem belajar dari
      catatan yang belum rapi adalah cara tercepat membuatnya{' '}
      <span style={{ color: 'var(--osd-text)', fontWeight: 600 }}>salah dengan percaya diri.</span>
    </p>
  </Frame>
);

const Closing: Page = () => (
  <div style={{ ...fill, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '0 140px' }}>
    <Eyebrow>SIGAP</Eyebrow>
    <h2
      style={{
        fontFamily: 'var(--osd-font-display)',
        fontSize: 96,
        fontWeight: 880,
        margin: '32px 0 0',
        letterSpacing: '-0.03em',
        lineHeight: 1.12,
        maxWidth: 1560,
      }}
    >
      Yang kami bangun bukan agen yang selalu menjawab.
    </h2>
    <p style={{ fontSize: 42, color: ink.soft, margin: '44px 0 0', maxWidth: 1480, lineHeight: 1.45 }}>
      Yang kami bangun adalah agen yang bisa dipercaya{' '}
      <span style={{ color: 'var(--osd-text)', fontWeight: 700 }}>saat</span> ia menjawab — karena ia
      menolak saat tidak layak.
    </p>
    <div style={{ height: 1, background: ink.rule, margin: '64px 0 0', width: 980 }} />
    <p style={{ fontSize: 28, color: ink.muted, margin: '36px 0 0', fontFamily: mono }}>
      Supply Disruption Intelligence &amp; Anticipation · SAP + AWS Hackathon Indonesia 2026
    </p>
  </div>
);

export const notes: (string | undefined)[] = [
  'Kalimat pembuka, dihafal: "SIGAP mengubah gangguan pasokan dari investigasi manual berhari-hari jadi satu rekomendasi siap-tanda-tangan dalam hitungan menit — tanpa membiarkan AI mengarang angka atau melanggar aturan." Jangan buka dengan daftar fitur.',
  'Lewati cepat. Ini penanda bagian, bukan konten.',
  `±50 detik. "Ini bukan masalah ERP yang kurang. Datanya sudah ada di S/4HANA."
Tekankan: yang hilang adalah jam-jam antara sinyal dan keputusan.
Kalau punya satu angka downtime milik perusahaan sendiri, sebut di sini — satu angka bersumber lebih kuat dari tiga tanpa sumber. Jangan sebut angka yang tak bisa kamu sebutkan sumbernya.`,
  'Tunjuk kotak terakhir yang merah. "Audit jadi rekonstruksi" — ini yang membuat direksi tidak percaya pada keputusan cepat.',
  'Ini dimensi yang khas Indonesia dan biasanya tak ada di produk global. TKDN menggerus karena impor; LARTAS menggeser tanggal, bukan harga. Dua-duanya menentukan apakah opsi boleh diambil, bukan apakah opsi itu murah.',
  'Penanda bagian. Lewati cepat.',
  '±60 detik. Satu beat per langkah, jangan berhenti lama. Yang penting: langkah 01 terjadi tanpa seorang pun login, dan langkah 06 yang biasanya hilang di produk lain.',
  `±40 detik. Jangan bacakan dua belas nama — tunjuk Kira yang merah.
"Yang membedakannya bukan jumlahnya, tapi satu agen punya hak veto, dan veto itu tidak bisa dibatalkan dengan alasan biaya."
Kalau ditanya jumlah tool: 46. Jangan taruh di slide.`,
  'Pintu kedua ini baru. Dulu jalur pengadaan bisa sampai ke draft PO tanpa pernah dinilai — harga lewat pintu belakang. Angka 12 dari 18 itu nyata, bukan ilustrasi.',
  'Penanda bagian. Lewati cepat.',
  `±60 detik. "Dua provider model dengan sengaja."
Beat utama: veto Kira, angka Tara, dan setiap label provenance itu Python — bukan instruksi ke model. Jadi spesialis boleh jalan di model murah tanpa satu pun jaminan melemah.`,
  'Diamkan sebentar, biarkan juri membaca. Kalau proyektornya kecil: jangan paksa baca label 10px — ceritakan saja alurnya dan sebut bahwa diagram ini digenerate dari kode, dengan assertion yang menolak label yang meluber.',
  'Kalau ada juri teknis, ini halaman yang mereka suka. Tak ada dependensi artinya tak ada yang bisa pensiun di tengah kompetisi.',
  `Pre-flight sebelum ke sini: 'manage.py check' bersih dan 'manage.py models --ping' menunjukkan 12 agen ready.
Pakai run cadangan kalau jaringan ragu. Jangan demo Ningbo dengan SAP_API_KEY terisi — opsi A–E ada di upload/fixture, bukan di tenant.`,
  'Penanda bagian. Ini bagian yang memenangkan juri — pelan sedikit.',
  'Lima label. Tunjuk yang dua terbawah: modelled dan missing. Produk lain tidak punya kosakata untuk mengaku.',
  'Beat: "menolak" itu kata kuncinya. Bacakan kalimat kuning itu apa adanya.',
  `±70 detik. HALAMAN TERPENTING.
HATI-HATI: dua angka Rp 70 juta di deck ini beda arti. Di halaman INI, Rp 70 jt = biaya rencana C+E yang dicoret. Di halaman Dampak nanti, Rp 70 jt = penghematan terhadap opsi A (Rp 186 jt). Jangan tertukar kalau juri bertanya.
"Pertanyaan yang biasanya tak terjawab: berapa harga kepatuhan itu?" Lalu tunjuk badge modelled — sistemnya mengaku sendiri, di halaman, di PDF, di email.`,
  'Singkat. "Approve dua kali tidak mengirim dua kali" biasanya memicu anggukan dari orang yang pernah kena.',
  'Ini jawaban untuk "sistemnya belajar?" — mencatat dan menampilkan, belum menggeser skor. Sebut bahwa itu pilihan sadar, bukan kekurangan.',
  'Beat: watcher sertifikat. Tak ada feed untuk kertas di lemari perusahaan sendiri. Ini yang membedakan "mengawasi dunia" dari "mengawasi kewajiban".',
  'Kalau juri skeptis soal kesiapan, jalankan perintahnya di depan mereka. 40 detik, dan lebih meyakinkan dari slide mana pun.',
  'Penanda bagian. Lewati cepat.',
  'INGAT: Rp 70 jt di sini adalah penghematan terhadap opsi A (Rp 186 jt dikurangi Rp 116 jt), bukan biaya C+E. Sebut "pada skenario ini" — jangan "rata-rata penghematan kami". Ini angka mekanisme, bukan angka pasar.',
  'Jangan buru-buru melewati halaman ini. Mengakui batas adalah bagian dari argumen, bukan pengurang nilai.',
  'Tunjuk langkah terakhir yang merah. Urutannya yang penting, bukan daftarnya.',
  'Berhenti di sini. Jangan tambah kalimat setelah kalimat terakhir di slide — biarkan menggantung, lalu tanya "ada pertanyaan?".',
];

export const meta: SlideMeta = {
  title: 'SIGAP — SAP + AWS Hackathon Indonesia 2026',
  createdAt: '2026-10-28T04:28:47.493Z',
};

export default [
  Cover,
  SectionProblem,
  ProblemClaim,
  ProblemTimeline,
  ProblemIndonesia,
  SectionSolution,
  SixSteps,
  TheTeam,
  TwoDoors,
  SectionArchitecture,
  TechStack,
  ArchitectureDiagram,
  StdlibOnly,
  DemoDivider,
  SectionTrust,
  Provenance,
  CalculatorRefuses,
  PriceOfRules,
  AuthorityLimits,
  ClosedLoop,
  Watchers,
  SelfChecked,
  SectionImpact,
  Impact,
  HonestState,
  Roadmap,
  Closing,
] satisfies Page[];
