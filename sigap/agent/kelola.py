"""Perkakas admin.

    python3 kelola.py pengguna budi@kpn.co.id "Budi Santoso" buyer rahasia123
    python3 kelola.py rahasia            # bikin SIGAP_SECRET
"""
import secrets
import sys

from core import identitas


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__); return
    p = sys.argv[1]
    if p == "rahasia":
        print(f'export SIGAP_SECRET="{secrets.token_hex(32)}"')
    elif p == "pengguna":
        email, nama, peran, sandi = sys.argv[2:6]
        u = identitas.tambah_pengguna(email, nama, peran, sandi)
        print(f"dibuat: {u.email} · {u.peran} · batas Rp {u.batas_idr:,}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
