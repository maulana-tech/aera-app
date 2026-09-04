# Inventaris repo referensi — `YUHAO-corn/manufacturing-agents`

> Hasil pembacaan langsung struktur & kode, 4 September 2026.
> Bukan ringkasan README — beberapa hal di README tidak cocok dengan isi kodenya.

## Metadata

| | |
|---|---|
| Deskripsi | Multi-agent LLM system for intelligent replenishment decisions in manufacturing supply chains |
| Bahasa | Python 3.10+ |
| Lisensi | **Apache-2.0** (boleh dipakai & diturunkan, wajib atribusi) |
| Bintang / fork | 172 / 24 |
| Dibuat | 24 Juli 2025 · commit terakhir 13 Maret 2026 |
| Ukuran | ~4,3 MB · **415 file** |
| Turunan dari | **[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** — diakui di README baris 402 (bagian 致谢, hanya bahasa Mandarin) |

## Peta direktori

| Direktori | File | KB | Isi |
|---|---:|---:|---|
| `manufacturingagents/` | 126 | 869 | Kode inti — **dua lapisan**, lihat di bawah |
| `tests/` | 117 | 825 | Test suite |
| `scripts/` | 52 | 293 | Deployment, docker, git fork tooling |
| `docs/` | 40 | 406 | Dokumentasi (punya CNAME → situs docs) |
| `web/` | 21 | 203 | Aplikasi Streamlit |
| `examples/` | 19 | 89 | Contoh pemakaian |
| `assets/` | 11 | 3.920 | Gambar |
| `utils/` | 9 | 50 | Skrip debug/perbaikan sekali pakai |
| `cli/` | 5 | 80 | Command-line interface |
| root | 13 | 58 | `main.py` `setup.py` `pyproject.toml` `requirements.txt` `requirements_db.txt` `docker-compose.yml` `.env.example` `CHANGELOG.md` `CONTRIBUTING.md` `VERSION` |

---

## LAPISAN 1 — warisan TradingAgents (di-rename)

Folder `manufacturingagents/` tingkat pertama. Ini kode trading yang di-*find-and-replace*
dari `tradingagents` → `manufacturingagents`. Nama filenya tidak diubah.

```
agents/analysts/     market_analyst · fundamentals_analyst · news_analyst
                     social_media_analyst · china_market_analyst
agents/researchers/  bull_researcher · bear_researcher
agents/risk_mgmt/    aggresive_debator · conservative_debator · neutral_debator
agents/managers/     research_manager · risk_manager
agents/trader/       trader.py
agents/utils/        agent_states · agent_utils · memory
graph/               trading_graph.py · setup · propagation · reflection
                     conditional_logic · signal_processing
dataflows/           yfin_utils · finnhub_utils · reddit_utils · googlenews_utils
                     stockstats_utils · tdx_utils · chinese_finance_utils
                     optimized_china_data · optimized_us_data · stock_api
                     stock_data_service · realtime_news_utils
                     adaptive_cache · cache_manager · integrated_cache · db_cache_manager
api/                 stock_api.py
config/              config_manager · database_config · database_manager · mongodb_storage
llm_adapters/        dashscope_adapter.py
```

**Bukti tambahan:**
- Typo `aggresive_debator` sama persis dengan repo asal
- Masih ada cache data saham nyata: `600519` (Kweichow Moutai), `300750` (CATL), `000001`
- `scripts/git/setup_fork_environment.sh`, `upstream_git_workflow.sh`,
  `development/prepare_upstream_contribution.py`, `maintenance/analyze_differences.ps1`
  → memang dikelola sebagai fork dengan sinkronisasi upstream
- Adaptasi A-share (TDX, DashScope, MongoDB/Redis, Streamlit) → kemungkinan turunan
  **TradingAgents-CN**, bukan TradingAgents langsung

---

## LAPISAN 2 — karya manufaktur asli

Folder bersarang `manufacturingagents/manufacturingagents/`. **Ini bagian yang benar-benar
mereka bangun**, dan domainnya memang supply chain.

### Agent

```
analysts/    market_environment_analyst      (+ varian _react)
             trend_prediction_analyst        (+ varian _react)
             industry_news_analyst_react
             consumer_insight_analyst_react
             sentiment_insight_analyst
             news_analyst
advisors/    optimistic_advisor              ← turunan bull_researcher
             cautious_advisor                ← turunan bear_researcher
coordinator/ decision_coordinator
risk_mgmt/   risk_assessment (+ _backup)
graph/       manufacturing_graph_react.py
```

### Alur sebenarnya (dari `manufacturing_graph_react.py`)

```
START → analis (SERIAL, add_edge berantai) → Optimistic_Advisor ⇄ Cautious_Advisor
      → Decision_Coordinator → Risk_Assessment → Conclusion_Extractor → END
```

`_should_continue_decision_debate()` membatasi **maksimal 2 ronde debat**
(optimis → hati-hati → optimis → hati-hati), dihitung per giliran, bukan berdasarkan
kecukupan bukti.

> ⚠️ **README tidak cocok dengan kode.** README menyebut enam agent: demand forecasting,
> cost analysis, supply chain coordination, market intelligence, decision, risk — dan
> menyiratkan kolaborasi paralel. Kodenya: empat analis serial + dua advisor + coordinator +
> risk + extractor. Node `cost analysis` dan `supply chain coordination` tidak ada.

### Data provider — 25 fungsi domain

| File | Fungsi |
|---|---|
| `supply_chain_data.py` | `get_supplier_info` `get_delivery_performance` `get_supply_risk_assessment` `get_supply_capacity_analysis` `get_alternative_suppliers` |
| `inventory_data.py` | `get_inventory_status` `get_inventory_turnover` `get_abc_analysis` `get_safety_stock_analysis` `get_inventory_aging_analysis` |
| `production_data.py` | `get_production_schedule` `get_production_capacity` `get_production_efficiency` `get_production_cost_analysis` `get_quality_metrics` `get_maintenance_schedule` |
| `demand_forecast_data.py` | `get_demand_forecast` `get_demand_trend_analysis` `get_market_demand_drivers` `get_demand_volatility_analysis` `get_demand_scenario_analysis` |
| `market_price_data.py` | harga & tren pasar |
| `manufacturing_data_adapter.py` | adapter gabungan |

Kosakatanya asli supply chain: ABC analysis, safety stock, inventory aging, OEE.
`get_alternative_suppliers` adalah padanan langsung `find_alternate_sources` milik SIGAP.

### 🚨 Temuan utama: seluruh data domain digenerate `random`

Jumlah pemakaian `random.` per file:

| File | Pemakaian |
|---|---:|
| `production_data.py` | 60 |
| `supply_chain_data.py` | 49 |
| `demand_forecast_data.py` | 37 |
| `market_price_data.py` | 32 |
| `inventory_data.py` | 25 |

Contoh nyata:

```python
'phone':           f'138{random.randint(10000000, 99999999)}',
'annual_revenue':  random.randint(1000000, 50000000),
'credit_rating':   random.choice(['AAA', 'AA', 'A', 'BBB']),
'payment_terms':   random.choice(['货到付款', '月结30天', '月结60天']),
```

**Tidak ada satu pun panggilan ERP.** Nomor telepon supplier pun dikarang.

Ironisnya ada `utils/strict_data_policy.py` dengan enum
`REAL_API / CACHED_DATA / SIMULATED_DATA / UNAVAILABLE` dan kebijakan *"hanya data sentimen
yang boleh fallback simulasi, sisanya wajib API nyata"* — kebijakan itu berlaku untuk lapisan
berita warisan trading, sementara seluruh data manufakturnya justru simulasi.

### Utilitas pendukung

```
prompts/           file .txt terpisah per agent + prompt_manager.py
                   advisors/ · analysts/ · coordinator/ · risk_mgmt/ · utils/
utils/             strict_data_policy · data_validator · tool_manager
                   preprocessing_assistant · conclusion_extractor
                   parameter_processor · prompt_utils · manufacturing_states
```

---

## `web/` — Streamlit (21 file)

```
app.py · run_web.py
components/   header · sidebar · analysis_form · results_display
pages/        cache_management · config_management · database_management
              token_statistics
i18n/         manufacturing_texts.py
utils/        analysis_runner · api_checker · progress_tracker
              simple_progress_tracker · text_manager · ui_utils
```

Yang menarik: **`progress_tracker`** dan callback `log_agent_start` / `log_agent_thinking` /
`log_api_call` / `log_agent_complete` — infrastruktur untuk menampilkan proses agent secara
live. Juga **`token_statistics`** — pelacakan biaya token per analisis.

## `tests/` — 117 file

Hanya **15** yang manufaktur, 15 lainnya warisan saham/trading, sisanya campuran:

```
tests/manufacturing/  test_end_to_end_manufacturing · test_four_analysts
                      test_manufacturing_agents · test_manufacturing_data_flow
                      test_manufacturing_data_layer · test_manufacturing_full_pipeline
                      test_manufacturing_graph · test_manufacturing_pipeline
                      test_manufacturing_react · test_real_manufacturing_flow
                      test_real_manufacturing_with_tools · test_specialized_tools
```

Ini test integrasi, **bukan eval suite skenario** — tidak ada yang menguji kualitas keputusan.

## `docs/` — 40 file

Mayoritas warisan trading: `agents/trader.md`, `usage/investment_analysis_guide.md`,
`troubleshooting/finnhub-news-data-setup.md`. Yang berguna secara struktur:
`architecture/system-architecture.md`, `graph-structure.md`, `data-flow-architecture.md`,
`development/project-structure.md`.

## `scripts/` — 52 file

`deployment/` (release GitHub) · `docker/` (start/stop, mongo-init) · `git/` (fork & upstream
workflow) · `development/` · `maintenance/`. Hampir semua infrastruktur, bukan domain.

---

## Penilaian

### Layak diambil

| Hal | Alasan | Effort |
|---|---|---|
| **Konsep provenance data** (`strict_data_policy`) | Ide bagus, eksekusi mereka gagal. Kalau SIGAP menerapkannya sungguhan → pembeda nyata | ½ hari |
| **`prompts/` sebagai .txt + prompt_manager** | Prompt jadi aset yang bisa direview, bukan string di kode | ~1 jam |
| **Callback progress agent** | Pola untuk UI agent trace live | ~2 jam |
| **Katalog 25 fungsi domain** | Peta gratis data apa saja yang relevan | gratis |
| **Konsep safety stock** | SIGAP pakai days-of-cover mentah; stockout efektif terjadi sebelum nol. Masuk ke `simulate_scenario`, **jangan tambah tool** | ½ hari |
| **Token statistics** | Melacak biaya per analisis — mendukung klaim unit economics di BMC | ~2 jam |

### Jangan diambil

- **Data provider berbasis `random`** — SIGAP pakai sandbox S/4HANA nyata
- **Alur serial tetap + debat dibatasi ronde** — bertentangan dengan runtime routing SIGAP
- **MongoDB + Redis** — berlebihan untuk cakupan ini
- **Warisan trading apa pun** — `trader.py`, `trading_graph.py`, YFinance, Finnhub, TDX
- **ABC analysis, inventory aging** — relevan untuk replenishment, tidak untuk respons disrupsi

### Posisi terhadap SIGAP

| | manufacturing-agents | SIGAP |
|---|---|---|
| Pemicu | Terjadwal — "saatnya evaluasi restock" | Kejadian — pelabuhan tutup, supplier gagal |
| Pertanyaan | Berapa banyak yang harus dipesan? | Rencana rusak, apa yang kita lakukan? |
| Keputusan | Optimis vs hati-hati, 2 ronde, koordinator memutus | Supervisor menyelidiki sampai bukti cukup |
| Kendala | Biaya & risiko | Biaya, risiko, **+ hukum kontrak yang bisa memveto** |
| Data | `random` | Sandbox S/4HANA + register resmi |

**Bukan pesaing ide kalian.** Planning versus disruption response — potongan masalah berbeda
di track yang sama.

### ⚠️ Catatan orisinalitas

Lisensi Apache-2.0, jadi menurunkan kode itu legal asal atribusi dicantumkan. Tapi hackathon
mensyaratkan *"original work created during the hackathon period"* — **ambil polanya, tulis
kodenya sendiri.** Repo ini juga contoh persis bagaimana proyek jadi janggal saat diperiksa:
nama folder bilang manufaktur, isinya `trader.py` dan cache saham Moutai. Jangan sampai ada
file nyasar semacam itu di repo SIGAP.
