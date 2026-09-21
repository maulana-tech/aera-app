"""Konfigurasi. Produksi menolak jalan dengan data contoh."""
from __future__ import annotations

import os
from dataclasses import dataclass


class KonfigurasiTidakSah(RuntimeError):
    pass


@dataclass(frozen=True)
class Konfigurasi:
    lingkungan: str          # "dev" | "staging" | "prod"
    sap_base_url: str
    sap_api_key: str
    aws_region: str
    model: str
    batas_otonom_idr: int
    batas_biaya_per_peristiwa_idr: int
    basis_data: str

    @property
    def produksi(self) -> bool:
        return self.lingkungan == "prod"

    @property
    def sap_siap(self) -> bool:
        return bool(self.sap_api_key)

    @property
    def model_siap(self) -> bool:
        return bool(self.aws_region)

    @property
    def boleh_pakai_contoh(self) -> bool:
        """Data contoh hanya untuk dev. Produksi tidak boleh menebak apa pun."""
        return not self.produksi


def muat() -> Konfigurasi:
    k = Konfigurasi(
        lingkungan=os.environ.get("SIGAP_ENV", "dev"),
        sap_base_url=os.environ.get("SAP_BASE_URL", "https://sandbox.api.sap.com"),
        sap_api_key=os.environ.get("SAP_API_KEY", ""),
        aws_region=os.environ.get("AWS_REGION", ""),
        model=os.environ.get("SIGAP_MODEL", "anthropic.claude-opus-5"),
        batas_otonom_idr=int(os.environ.get("SIGAP_BATAS_OTONOM_IDR", "50000000")),
        batas_biaya_per_peristiwa_idr=int(os.environ.get("SIGAP_BATAS_BIAYA_IDR", "500000")),
        basis_data=os.environ.get("SIGAP_DB", "data/sigap.db"),
    )
    if k.produksi:
        kurang = []
        if not k.sap_api_key:
            kurang.append("SAP_API_KEY")
        if not k.aws_region:
            kurang.append("AWS_REGION")
        if kurang:
            raise KonfigurasiTidakSah(
                "SIGAP_ENV=prod tapi belum lengkap: " + ", ".join(kurang) +
                ". Produksi tidak boleh jalan dengan data contoh."
            )
    return k


KONF = muat()
