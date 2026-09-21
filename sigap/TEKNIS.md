# Catatan Teknis

> Lampiran untuk `PLAN.md`. Isinya cuma hal yang perlu nama fungsi dan parameter persis —
> semua penjelasan konsep ada di `PLAN.md`.

## Memanggil Claude lewat Bedrock

```python
from anthropic import AnthropicBedrockMantle

client = AnthropicBedrockMantle(aws_region="us-west-2")   # cek region dulu

resp = client.messages.create(
    model="anthropic.claude-opus-5",        # awalan "anthropic." wajib di Bedrock
    max_tokens=16000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},       # di dalam output_config, bukan top-level
    tools=TOOLS,
    messages=messages,
)
```

**Yang sering salah:**

| Salah | Benar | Akibat |
|---|---|---|
| `AnthropicBedrock(...)` | `AnthropicBedrockMantle(...)` | Yang lama jalur InvokeModel, bukan Messages API |
| `model="claude-opus-5"` | `model="anthropic.claude-opus-5"` | Nama model ditolak di Bedrock |
| `thinking={"type":"enabled","budget_tokens":N}` | `thinking={"type":"adaptive"}` | **Error 400** di Opus 5 |
| `effort="high"` di top-level | di dalam `output_config` | Parameter diabaikan |

## Effort per agent

| Agent | Effort | Alasan |
|---|---|---|
| Ketua (supervisor) | `high` | Dia yang memilih rute dan menilai kecukupan bukti |
| Ahli Aturan | `high` | Keputusan veto tidak boleh salah |
| Ahli lainnya | `medium` | Tugasnya sempit dan jelas |

Pakai **streaming** untuk ketua — gilirannya panjang, tanpa streaming bisa kena batas waktu HTTP.

```python
with client.messages.stream(model=..., max_tokens=64000, ...) as stream:
    resp = stream.get_final_message()
```

## Hemat biaya: prompt caching

Urutan pengiriman: `tools` → `system` → `messages`. Taruh yang **tidak berubah** di depan.
Satu byte berubah di bagian depan membatalkan cache seluruh sisanya.

Di tim agent, daftar alat dan instruksi dikirim ulang **setiap** agent bekerja — tanpa caching,
biayanya berlipat sebanyak jumlah agent.

```python
resp = client.messages.create(
    ...,
    cache_control={"type": "ephemeral"},
)
print(resp.usage.cache_read_input_tokens)   # kalau nol terus → ada yang membatalkan cache
```

Penyebab cache batal yang paling sering: `datetime.now()` di instruksi, urutan daftar alat yang
berubah-ubah, atau ID acak di bagian depan.

## Kalau biaya perlu ditekan

Ahli-ahli bisa dipindah ke `anthropic.claude-sonnet-5`, sementara ketua dan Ahli Aturan tetap
Opus 5.

**Jangan lakukan sebelum diukur.** Dua catatan: cache bersifat per-model, jadi memakai dua model
membuang penggunaan ulang cache; dan permintaan yang lebih murah tapi butuh lebih banyak putaran
tidak benar-benar lebih murah.

## Penanda asal data

Satu pembungkus, dipakai semua alat. Tulis ini sebelum alat kedua dibuat.

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Any

class Asal(Enum):
    LANGSUNG = "live"        # diambil dari SAP / API resmi
    SIMPANAN = "cached"      # pernah langsung, ada waktunya
    HITUNGAN = "derived"     # dihitung dari yang langsung
    CONTOH   = "modelled"    # profil perusahaan — ditandai terbuka
    TIDAK_ADA = "missing"    # ketua berhenti, tidak menebak

@dataclass
class Hasil:
    nilai: Any
    asal: Asal
    sumber: str              # "API_MATERIAL_STOCK_SRV" / "register TKDN"
    diambil: datetime
```

**Aturannya:** kalau masukan di jalur penting bernilai `TIDAK_ADA` atau `CONTOH`, kalkulator
biaya **tidak boleh** mengeluarkan angka penghematan. Ketua melaporkan apa yang kurang.

## Batas supaya tim agent tidak berputar

Pasang sejak agent kedua dibuat:

- Batas jumlah oper-operan antar ahli
- Batas total putaran ketua
- Batas waktu keseluruhan

Setiap sistem tim agent punya batas semacam ini, dan alasannya sama: tanpa itu, mereka bisa
saling melempar tanpa henti.

## Kenapa satu program dulu, bukan cloud

```
# ponytail: satu proses Python; pecah ke Lambda per alat kalau butuh skala atau isolasi
```

23 fungsi terpisah di cloud sejak hari pertama membuat tiap perubahan kecil butuh deploy.
Untuk presentasi, satu program biasa sudah cukup. Pindah ke cloud setelah Tahap 7 lulus.

## Yang dipasang

```bash
pip install anthropic boto3 strands-agents httpx pydantic
npm install twenty-ui react@^19 react-dom@^19    # tampilan; kunci versinya, masih alpha
```
