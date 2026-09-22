export const HULU = process.env.SIGAP_API ?? "http://127.0.0.1:8787";

export type Langkah = {
  urutan: number; tahap: string; agent: string; agent_nama: string;
  ringkas: string; alat: string[]; asal: string | null; sumber: string | null;
  detail: Record<string, unknown>; waktu: string;
};
export type Aksi = {
  id: string; jenis: string; otonom: number; status: string;
  muatan: Record<string, any>; referensi_sap: string | null; dibuat: string;
};
export type Persetujuan = {
  id: number; aksi_id: string; oleh: string; peran: string;
  putusan: string; catatan: string | null; waktu: string;
};
export type Jalan = {
  id: string; judul: string; jenis: string; pemicu: string;
  mode: "otonom" | "runut"; status: string; mulai: string; selesai: string | null;
  biaya_token_idr: number; keputusan: Record<string, any> | null; galat: string | null;
  langkah?: Langkah[]; aksi?: Aksi[]; persetujuan?: Persetujuan[];
};

export const ASAL: Record<string, { label: string; cls: string }> = {
  live:     { label: "langsung",  cls: "border-emerald-500/40 text-emerald-300 bg-emerald-500/10" },
  cached:   { label: "simpanan",  cls: "border-sky-500/40 text-sky-300 bg-sky-500/10" },
  derived:  { label: "hitungan",  cls: "border-violet-500/40 text-violet-300 bg-violet-500/10" },
  modelled: { label: "contoh",    cls: "border-amber-500/50 text-amber-300 bg-amber-500/10" },
  missing:  { label: "tidak ada", cls: "border-rose-500/50 text-rose-300 bg-rose-500/10" },
};

export const STATUS: Record<string, string> = {
  berjalan: "border-sky-500/40 text-sky-300 bg-sky-500/10",
  selesai:  "border-emerald-500/40 text-emerald-300 bg-emerald-500/10",
  ditahan:  "border-amber-500/50 text-amber-300 bg-amber-500/10",
  gagal:    "border-rose-500/50 text-rose-300 bg-rose-500/10",
  menunggu: "border-amber-500/50 text-amber-300 bg-amber-500/10",
  disetujui:"border-emerald-500/40 text-emerald-300 bg-emerald-500/10",
  ditolak:  "border-rose-500/50 text-rose-300 bg-rose-500/10",
  terkirim: "border-emerald-500/40 text-emerald-300 bg-emerald-500/10",
};

export const rupiah = (n: number) => "Rp " + (n ?? 0).toLocaleString("id-ID");

export type Saya = { nama: string; email: string; peran: string; batas_idr: number };

/** Ambil dari layanan agent dengan token sesi dari cookie httpOnly. */
export async function ambil<T>(jalur: string): Promise<T | null> {
  const { cookies } = await import("next/headers");
  const token = (await cookies()).get("sigap_sesi")?.value;
  try {
    const r = await fetch(`${HULU}/${jalur}`, {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

export async function saya(): Promise<Saya | null> {
  return ambil<Saya>("saya");
}

export type Alat = { nama: string; terpasang: boolean; deskripsi: string | null };
export type Agent = {
  kode: string; nama: string; peran: string; effort: string;
  veto: boolean; ketua: boolean; alat: Alat[];
  terpasang: number; total_alat: number; dipakai_di: number;
};
export type RingkasAgent = {
  jumlah_agent: number; alat_terpasang: number; alat_total: number;
  model_siap: boolean; sap_siap: boolean;
};
