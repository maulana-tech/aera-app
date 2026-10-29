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
        Gangguan pasok yang ditangani sebelum orang pertama menyadarinya
      </h2>
      <Body style={{ marginTop: 24, maxWidth: 640, fontSize: 24 }}>
        Dua belas agen membaca SAP, mematuhi TKDN dan LARTAS, lalu menaruh satu
        keputusan yang bisa disetujui di meja Anda.
      </Body>
      <div style={{ marginTop: 32 }}>
        <Pill>Tim Socrates</Pill>
        <Pill>APP Group</Pill>
        <Pill red>Live demo</Pill>
      </div>
    </div>
  </div>
);

const Problem: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>01 · Masalah</Eyebrow>
      <Title>Masalahnya bukan kecepatan saja</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 476, width: ZONE.tall.width,
      display: 'grid', gap: 26,
    }}>
      <Step n="1" head="Kabar sampai lewat jalur yang salah">
        Berita, grup WhatsApp, telepon dari forwarder.
      </Step>
      <Step n="2" head="Tiga hari menelusuri manual">
        Excel, email, tanya satu-satu: order mana yang kena.
      </Step>
      <Step n="3" head="Keputusan dari data basi">
        Angkanya sudah berubah sejak Selasa.
      </Step>
      <Step n="4" head="Lalu jejaknya hilang">
        Tak ada catatan dasar keputusan. Audit jadi rekonstruksi.
      </Step>
    </div>
    <OnGradient top={470} kicker="Yang sebenarnya mahal">
      Keputusan tercepat sering justru yang paling tidak boleh diambil.
      <span style={{ display: 'block', marginTop: 18, fontSize: 24, fontWeight: 400 }} />
    </OnGradient>
    <OnGradient top={660} kicker="" sub="Datanya sudah ada di S/4HANA. Yang hilang adalah jam-jam di antara sinyal dan keputusan.">
      <span style={{ fontSize: 26, fontWeight: 400, color: ink.onDark }}>
        Ini bukan masalah ERP yang kurang.
      </span>
    </OnGradient>
    <Footer label="Masalah" />
  </div>
);

const Rules: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>01 · Masalah</Eyebrow>
      <Title>Dua aturan yang membuat opsi termurah jadi terlarang</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 506, width: ZONE.tall.width,
      display: 'grid', gap: 30,
    }}>
      <div>
        <div style={{ fontSize: 27, fontWeight: 800 }}>TKDN</div>
        <Small style={{ marginTop: 6, fontSize: 22 }}>
          Tingkat Komponen Dalam Negeri. Beralih ke supplier impor menggerus
          angkanya — dan kontraknya punya lantai.
        </Small>
      </div>
      <div>
        <div style={{ fontSize: 27, fontWeight: 800 }}>LARTAS</div>
        <Small style={{ marginTop: 6, fontSize: 22 }}>
          Larangan &amp; Pembatasan impor. Origin baru butuh izin yang tidak
          terbit dalam seminggu.
        </Small>
      </div>
      <div style={{ borderTop: `1px solid ${ink.rule}`, paddingTop: 22 }}>
        <Small style={{ fontSize: 21 }}>
          Mempercepat keputusan tanpa menegakkan dua aturan ini bukan kemajuan.
          Itu mempercepat pelanggaran kontrak.
        </Small>
      </div>
    </div>
    <OnGradient
      top={520}
      kicker="Contoh nyata dari demo"
      sub="Bukan karena mahal. Karena melanggar — dan harga tidak membatalkan aturan.">
      Opsi E — Rp 48 juta, yang termurah — dicoret.
      <span style={{ display: 'block', marginTop: 14, fontSize: 28, fontWeight: 400, color: ink.onDarkMuted }}>
        TKDN jatuh ke 34,8%.
      </span>
    </OnGradient>
    <Footer label="Masalah" />
  </div>
);

const Solution: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>02 · Solusi</Eyebrow>
      <Title>Dua belas agen, satu keputusan yang bisa disetujui</Title>
      <Rule />
    </div>
    {/* Five steps have to clear the partner logos at y=912, so they start
        higher and sit tighter than the four-step pages. */}
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 452, width: ZONE.tall.width,
      display: 'grid', gap: 16,
    }}>
      <Step n="01" head="Watcher, bukan inbox">
        BMKG, GDACS, NASA EONET, USGS, Open-Meteo — tanpa diminta.
      </Step>
      <Step n="02" head="Dua belas agen membaca">
        S/4HANA, master data, upload, feed publik.
      </Step>
      <Step n="03" head="Kira mencoret yang melanggar">
        TKDN dan LARTAS, sebelum harga ikut bicara.
      </Step>
      <Step n="04" head="Tara memberi angka">
        Biaya, tanggal habis stok, OTIF, dampak TKDN.
      </Step>
      <Step n="05" head="Mengeksekusi dalam batas wewenang">
        Di atasnya, berhenti dan bertanya.
      </Step>
    </div>
    <OnGradient
      top={500}
      kicker="Satu agen punya hak veto"
      sub="Vetonya bukan prompt. Ia membaca rule pack, dan penolakannya tidak bisa dibatalkan oleh harga.">
      Kira menolak di dua pintu — saat opsi dipilih, dan lagi saat PO diterbitkan.
    </OnGradient>
    <Footer label="Solusi" />
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
      <Eyebrow>03 · Arsitektur</Eyebrow>
      <h1 style={{
        margin: '12px 0 0', fontSize: 44, fontWeight: 800, letterSpacing: '-0.02em',
      }}>
        AWS untuk otaknya, SAP untuk datanya dan pintunya
      </h1>
    </div>
    <img
      src={architecture}
      alt="Arsitektur SIGAP: AWS Bedrock dan AgentCore di sisi model, SAP S/4HANA dan AI Core di sisi data"
      style={{
        position: 'absolute', left: 136, top: 398, width: 1648, height: 398,
        objectFit: 'contain',
      }}
    />
    <div style={{ position: 'absolute', left: 136, top: 810, width: 1200 }}>
      <Small style={{ fontSize: 18 }}>
        Agent service: Python 3, standard library saja — <span style={{ fontFamily: mono }}>http.server</span>{' '}
        + <span style={{ fontFamily: mono }}>sqlite3</span>. Digambar oleh{' '}
        <span style={{ fontFamily: mono }}>sigap/architecture/diagram.py</span>, bukan tangan.
      </Small>
    </div>
  </div>
);

const Demo: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 380, width: ZONE.tall.width }}>
      <Eyebrow>Jeda</Eyebrow>
      <div style={{
        fontSize: 108, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 0.96,
        marginTop: 18,
      }}>
        Demo
        <span style={{ color: ink.red }}>.</span>
      </div>
      <Rule />
      <Body style={{ marginTop: 26, fontSize: 24 }}>
        Satu topan menutup Ningbo. Kita lihat SIGAP menemukannya, menilainya,
        menolak opsi termurah, lalu berhenti meminta tanda tangan.
      </Body>
    </div>
    <OnGradient
      top={430}
      kicker="Yang akan Anda lihat"
      sub="Semua angka di layar bisa dihitung ulang dari perintah di DEMO.md.">
      Live, bukan rekaman — terhadap SAP S/4HANA dan Amazon Bedrock yang sebenarnya.
    </OnGradient>
  </div>
);

const Trust: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>04 · Kenapa bisa dipercaya</Eyebrow>
      <Title>Agen lain menjawab dengan percaya diri</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 452, width: ZONE.tall.width,
      display: 'grid', gap: 18,
    }}>
      <Step n="01" head="Tiap angka membawa asalnya">
        <span style={{ fontFamily: mono, fontSize: 19 }}>live · uploaded · derived · modelled · missing</span>
        {' '}— terbaca di layar, bukan di log.
      </Step>
      <Step n="02" head="Kalkulatornya menolak menebak">
        Tanpa data yang layak, ia mengembalikan <span style={{ fontFamily: mono, fontSize: 19 }}>missing</span>,
        bukan angka yang terdengar meyakinkan.
      </Step>
      <Step n="03" head="Veto ada di kode, bukan di prompt">
        Dari 18 supplier: 6 domestik lolos, 12 asing diblok.
      </Step>
      <Step n="04" head="56 modul memeriksa dirinya sendiri">
        <span style={{ fontFamily: mono, fontSize: 19 }}>manage.py check</span> — 0 gagal.
      </Step>
    </div>
    <OnGradient
      top={500}
      kicker="Bedanya"
      sub="Itulah syarat sebuah agen boleh menyentuh purchase order sungguhan.">
      Yang ini menolak menjawab kalau datanya tidak layak.
    </OnGradient>
    <Footer label="Kepercayaan" />
  </div>
);

const Numbers: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>04 · Kenapa bisa dipercaya</Eyebrow>
      <Title>Angka yang bisa dihitung ulang</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 492, width: ZONE.tall.width,
      display: 'grid', gap: 0,
    }}>
      {[
        ['Rp 116 jt', 'opsi B+C yang dipilih · TKDN 41,6%'],
        ['Rp 70 jt', 'lebih hemat dari opsi A (38%)'],
        ['Rp 46 jt', 'harga kepatuhan — dan kami tunjukkan'],
      ].map(([n, c], i) => (
        <div key={n} style={{
          display: 'flex', alignItems: 'baseline', gap: 24, padding: '10px 0',
          borderTop: i === 0 ? 'none' : `1px solid ${ink.rule}`,
        }}>
          <div style={{
            fontSize: 52, fontWeight: 800, letterSpacing: '-0.03em', minWidth: 230,
            color: i === 2 ? ink.red : 'var(--osd-text)',
          }}>{n}</div>
          <div style={{ fontSize: 21, lineHeight: 1.4, color: ink.muted }}>{c}</div>
        </div>
      ))}
    </div>
    <div style={{ position: 'absolute', left: ZONE.tall.left, top: 800, width: ZONE.tall.width }}>
      <Small style={{ fontSize: 19 }}>
        Keluar dari <span style={{ fontFamily: mono }}>engine/simulate.py</span>, bukan dari model.
      </Small>
    </div>
    <OnGradient
      top={500}
      kicker="Harga kepatuhan"
      sub="Sistem lain menyembunyikan selisih ini. Kami menuliskannya, karena itulah yang ditandatangani seorang approver.">
      Menaati TKDN memang lebih mahal. Rp 46 juta lebih mahal.
    </OnGradient>
    <Footer label="Kepercayaan" />
  </div>
);

const Honest: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 244, width: ZONE.wide.width }}>
      <Eyebrow>05 · Dampak</Eyebrow>
      <Title>Sudah jalan hari ini — dan kami tahu persis apa yang belum</Title>
      <Rule />
    </div>
    <div style={{
      position: 'absolute', left: ZONE.tall.left, top: 516, width: ZONE.tall.width,
      display: 'grid', gap: 22,
    }}>
      <div>
        <div style={{ fontSize: 23, fontWeight: 800, color: '#1A7F4B' }}>Jalan</div>
        <Small style={{ marginTop: 6, fontSize: 21 }}>
          SAP S/4HANA live, Bedrock dan AI Core, 46 tool, 12 prompt, lima watcher,
          delapan job terjadwal, laporan PDF dan XLSX, deploy terotomasi.
        </Small>
      </div>
      <div>
        <div style={{ fontSize: 23, fontWeight: 800, color: ink.red }}>Belum</div>
        <Small style={{ marginTop: 6, fontSize: 21 }}>
          Rule pack masih bernilai ilustratif — tiap aturan sudah membawa{' '}
          <span style={{ fontFamily: mono, fontSize: 19 }}>verified</span>, dan semuanya
          masih <span style={{ fontFamily: mono, fontSize: 19 }}>false</span>. SQLite perlu
          pindah ke Postgres sebelum apa pun yang nyata.
        </Small>
      </div>
    </div>
    <OnGradient
      top={500}
      kicker="Kenapa ini ada di slide"
      sub="Produk yang menolak menebak tidak boleh menebak tentang dirinya sendiri.">
      Daftar &ldquo;belum&rdquo; itu bagian dari argumennya, bukan catatan kaki.
    </OnGradient>
    <Footer label="Dampak" />
  </div>
);

const Closing: Page = () => (
  <div style={fill}>
    <div style={{ position: 'absolute', left: 80, top: 300, width: ZONE.tall.width }}>
      <Eyebrow>Satu kalimat untuk diingat</Eyebrow>
      <h1 style={{
        margin: '22px 0 0', fontSize: 50, lineHeight: 1.14, fontWeight: 800,
        letterSpacing: '-0.02em',
      }}>
        Bukan agen yang memutuskan lebih cepat — agen yang menolak memutuskan
        hal yang tidak boleh.
      </h1>
      <Rule width={150} />
      <Body style={{ marginTop: 28, fontSize: 23 }}>
        Keputusan yang bisa disetujui, dengan asal tiap angkanya, dalam hitungan
        menit, dan tidak pernah melanggar TKDN atau LARTAS.
      </Body>
      <div style={{ marginTop: 30, fontFamily: mono, fontSize: 20, color: ink.muted }}>
        sigap.lumbungstack.dev
      </div>
    </div>
    <OnGradient
      top={470}
      kicker="Tim Socrates"
      sub="Terima kasih — dan silakan minta kami menjalankan ulang perintah mana pun yang angkanya tadi muncul di layar.">
      Siap menerima pertanyaan.
    </OnGradient>
  </div>
);

/* ------------------------------------------------------------------ notes */

export const notes: (string | undefined)[] = [
  'Halo, kami Tim Socrates. SIGAP: gangguan pasok yang ditangani sebelum orang pertama menyadarinya. Sepuluh halaman, dan salah satunya demo langsung. Mulai dari kenapa ini sulit.',
  'Saat satu pelabuhan tutup, puluhan material berhenti. Yang mahal bukan topannya — tiga hari menelusuri Excel dan WhatsApp, lalu memutuskan dari angka yang sudah basi, dan tak ada jejak kenapa. Datanya sudah ada di S/4HANA. Yang hilang adalah jam-jam di antara sinyal dan keputusan.',
  'Dan ada dimensi yang khas Indonesia. Opsi termurah hampir selalu impor; impor menggerus TKDN dan kena LARTAS. Di demo nanti opsi E — yang termurah, Rp 48 juta — dicoret karena TKDN jatuh ke 34,8%. Bukan karena mahal. Karena melanggar. Jadi mempercepat keputusan tanpa menegakkan aturan ini bukan kemajuan.',
  'SIGAP menutup jam-jam itu. Watcher memantau BMKG, GDACS, NASA EONET, USGS dan Open-Meteo tanpa diminta. Dua belas agen membaca SAP dan data pendukung. Kira mencoret yang melanggar sebelum harga ikut bicara — dan vetonya ada di dua pintu, saat opsi dipilih dan lagi saat PO diterbitkan. Tara memberi angka. Lalu sistem mengeksekusi dalam batas wewenang, dan berhenti bertanya di atasnya.',
  'Arsitekturnya: AWS untuk otaknya — Bedrock dan AgentCore — SAP untuk datanya dan pintunya, S/4HANA dan AI Core. Agent service-nya Python standard library saja, http.server dan sqlite3; tidak ada orkestrator, tidak ada message broker. Diagram ini digenerate dari kode, bukan digambar tangan.',
  'Sekarang demonya. Satu topan menutup Ningbo. Live terhadap SAP dan Bedrock sungguhan. Perhatikan tiga hal: dari mana tiap angka berasal, di mana Kira mencoret, dan di mana sistem berhenti meminta tanda tangan.',
  'Yang baru saja Anda lihat sulitnya di sini. Tiap angka membawa asalnya — live, uploaded, derived, modelled, missing — dan itu tampil di layar, bukan tersembunyi di log. Kalkulatornya menolak menebak: tanpa data layak ia mengembalikan missing. Vetonya ada di kode. Dan 56 modul memeriksa dirinya sendiri, nol gagal.',
  'Angkanya bisa dihitung ulang. Opsi B+C: Rp 116 juta, TKDN 41,6% — hemat Rp 70 juta dibanding opsi A. Dan yang paling jarang ditunjukkan orang: harga kepatuhan, Rp 46 juta. Menaati TKDN memang lebih mahal, dan kami menuliskannya, karena itulah yang ditandatangani seorang approver.',
  'Yang jalan hari ini: SAP live, dua provider model, 46 tool, lima watcher, delapan job, laporan, deploy otomatis. Yang belum: rule pack masih ilustratif — tiap aturan sudah membawa flag verified, dan semuanya masih false — dan SQLite harus pindah ke Postgres sebelum apa pun yang nyata. Kami taruh ini di slide karena produk yang menolak menebak tidak boleh menebak tentang dirinya sendiri.',
  'Satu kalimat: ini bukan agen yang memutuskan lebih cepat, tapi agen yang menolak memutuskan hal yang tidak boleh. Keputusan yang bisa disetujui, dengan asal tiap angkanya, dalam hitungan menit. Silakan minta kami menjalankan ulang perintah mana pun yang angkanya muncul tadi. Terima kasih.',
];

export const meta: SlideMeta = {
  title: 'SIGAP — 10 halaman, template panitia',
  createdAt: '2026-10-29T00:34:00.000Z',
};

export default [
  Cover,
  Problem,
  Rules,
  Solution,
  Architecture,
  Demo,
  Trust,
  Numbers,
  Honest,
  Closing,
] satisfies Page[];
