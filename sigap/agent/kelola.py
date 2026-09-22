"""Perkakas admin.

    python3 kelola.py pengguna budi@kpn.co.id "Budi Santoso" buyer rahasia123
    python3 kelola.py rahasia            # bikin SIGAP_SECRET
    python3 kelola.py periksa            # apa yang masih kurang
"""
import secrets
import subprocess
import sys

from core import identitas

# Berkas yang punya pemeriksaan sendiri di blok __main__-nya.
PERIKSA = [
    "core/provenance.py", "core/registry.py", "core/identitas.py",
    "engine/simulate.py", "tools/compliance.py", "agents/definisi.py",
]


def periksa() -> None:
    """Jalankan semua pemeriksaan, lalu sebutkan yang belum ada."""
    gagal = []
    for f in PERIKSA:
        r = subprocess.run([sys.executable, f], capture_output=True, text=True,
                           env={**__import__("os").environ, "PYTHONPATH": "."})
        print(f"  {'ok    ' if r.returncode == 0 else 'GAGAL '} {f}")
        if r.returncode:
            gagal.append(f)
            print("        " + (r.stderr.strip().splitlines() or [""])[-1])

    from agents.definisi import SEMUA
    from core import konfigurasi, registry
    import tools.impact, tools.sourcing, tools.compliance, tools.lainnya, tools.simulasi  # noqa

    pasang = registry.semua()
    tanpa_prompt = [a for a in SEMUA.values() if not a.siap]
    tanpa_alat = {a.panggilan: [n for n in a.alat if n not in pasang]
                  for a in SEMUA.values() if any(n not in pasang for n in a.alat)}
    dideklarasi = sum(len(a.alat) for a in SEMUA.values())

    print(f"\n  agent   : {len(SEMUA)}")
    print(f"  alat    : {len(pasang)}/{dideklarasi} terpasang")
    print(f"  prompt  : {len(SEMUA) - len(tanpa_prompt)}/{len(SEMUA)} ditulis")

    if tanpa_prompt:
        print("\n  instruksi belum ditulis:")
        for a in tanpa_prompt:
            print(f"    · prompts/{a.kode}.txt — {a.panggilan} ({a.nama})")
    if tanpa_alat:
        print("\n  alat belum ditulis:")
        for nm, ns in tanpa_alat.items():
            print(f"    · {nm}: {', '.join(ns)}")

    K = konfigurasi.KONF
    kurang = [n for n, v in (("SAP_API_KEY", K.sap_api_key), ("AWS_REGION", K.aws_region)) if not v]
    if kurang:
        print(f"\n  kunci belum diisi: {', '.join(kurang)}"
              "\n    tanpa ini sistem menolak memutuskan apa pun — itu memang disengaja.")

    if gagal:
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__); return
    p = sys.argv[1]
    if p == "periksa":
        periksa()
    elif p == "rahasia":
        print(f'export SIGAP_SECRET="{secrets.token_hex(32)}"')
    elif p == "pengguna":
        email, nama, peran, sandi = sys.argv[2:6]
        u = identitas.tambah_pengguna(email, nama, peran, sandi)
        print(f"dibuat: {u.email} · {u.peran} · batas Rp {u.batas_idr:,}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
