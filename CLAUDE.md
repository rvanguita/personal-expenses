# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Web app for ingesting, categorizing (via Google Gemini AI), and analyzing personal credit card
expenses, backed by a MySQL **Medallion Architecture** (Raw → Bronze → Silver). Package/dependency
management is via `uv`.

**Two frontends, one dashboard:**
- `main.py` — **Streamlit** (`src/expenses/ui/`), port `8503`, two pages via `st.navigation`:
  **Dashboard** (`ui/dashboard_page.py`) and **Dados** (`ui/data_page.py`, the write paths).
- `dash_app.py` — **Dash**, port `DASH_PORT` (default `8050`), the same dashboard read-only;
  styles in `assets/dashboard.css`.

Both render the framework-agnostic layer in `src/expenses/dashboard/`: `data.build_view(df_full,
period, holders, categories) -> DashboardView` (only calls `analytics.py` / `filters.py`),
`data.kpi_cards(view)`, `figures.py` (Plotly builders) and `theme.py` (design tokens). **Add new
numbers to `build_view` and new charts to `dashboard/figures.py`, then render them in both
frontends.** `src/expenses/dashboard/` must never import Streamlit or Dash (enforced by
`tests/test_app_imports.py`).

The former Streamlit coupling in `database.py` / `parser.py` / `ai_categorizer.py` lives behind
`src/expenses/runtime.py` (`cache_data`, `cache_resource`, `clear_caches`, `notify_error`,
`notify_warning`) — **never re-add `import streamlit` to those three modules** (the pure-Python
test suite imports them with no Streamlit runtime).

## Commands

```bash
# Install dependencies (including dev group)
uv sync --all-groups

# Run the Streamlit app (port 8503, from .env STREAMLIT_PORT)
uv run streamlit run main.py

# Run the Dash app (port 8050, from .env DASH_PORT)
uv run python dash_app.py

# Run all tests
uv run pytest

# Run a single test file / test
uv run pytest tests/test_analytics.py
uv run pytest tests/test_analytics.py::test_calculate_kpis_basic

# Lint + format (both enforced in CI)
uv run ruff check .
uv run ruff format .            # CI runs `ruff format --check .`

# Docker Compose (`streamlit` = :8503, `dash` = :8050, same image)
docker compose up --build -d
docker compose logs -f streamlit
# After renaming/removing a service, drop the old fixed-name container once:
docker compose down --remove-orphans
```

CI (`.github/workflows/ci.yml`) runs on **every branch push**, **every PR**, and manual dispatch
(per-ref `concurrency` cancels superseded runs): `uv sync --all-groups --locked` (fails on
`pyproject`/`uv.lock` drift, matching the Dockerfile's `--frozen`), `uv run ruff check .`,
`uv run ruff format --check .`, then `uv run pytest`.

Environment variables live in `.env` (see `.env.example`): `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`,
`MYSQL_PASSWORD`, `MYSQL_TABLE` (unified table name across all three DBs), `MYSQL_DB_RAW`,
`MYSQL_DB_BRONZE`, `MYSQL_DB_SILVER`, `GEMINI_API_KEY`, `GEMINI_MODEL`,
`REFERENCE_BUDGET_LIMIT`, `CATEGORY_LOCAL_PATH`, `STREAMLIT_PORT`, `DASH_PORT`.
Tests do not require a live MySQL/Gemini connection — they exercise pure data-transform functions.
**Do not run ad-hoc scripts that call `database.py` write helpers** (`ingest_raw_bronze`,
`save_dataframe_replace`, `repopulate_silver_layer`, `deduplicate_all_layers`): if `.env` points at a
reachable DB they will mutate it. Monkeypatch `get_db_engine` to return `None` first.

## Architecture

### Medallion pipeline (Raw → Bronze → Silver)

Three separate MySQL **databases** (not just tables), all sharing the same table name
(`MYSQL_TABLE`, default `personal_expenses`), configured in `src/expenses/config.py` and provisioned by
`src/expenses/database.py::create_medallion_tables()`:

- **Raw** (`src/expenses/parser.py::parse_raw_csv`) — exact strings from the uploaded CSV, columns
  prefixed `raw_*`, no type coercion. Column detection is done by fuzzy keyword matching against header
  names (handles Portuguese/English header variants like `Data`/`date`, `Estabelecimento`/`merchant`).
- **Bronze** (`src/expenses/parser.py::transform_raw_to_bronze`) — cleaned/typed: dates parsed
  (`date` = invoice date from filename or fallback, `date_buy` = purchase date, `dayfirst=True`), costs
  converted from Brazilian `R$ 1.234,56` format to float, installments parsed from `"1 de 3"` / `"1/3"`
  patterns into `installment`/`total_installments` ints, merchant `id` upper-cased/stripped.
- **Silver** (`src/expenses/ai_categorizer.py`) — Bronze data enriched with `category`, `motivation`, and
  `categorized_by` (`history_match` | `dictionary_match` | `gemini_ai` | `pending`). This is the only
  layer the dashboard reads from (`database.py::load_expenses_data`).

Each layer's schema is defined and auto-migrated (`ALTER TABLE ADD COLUMN` for any missing column) by
`create_medallion_tables()` / `align_table_columns()` — called defensively at the top of most read/write
functions, so schema changes should be made by editing the column dicts in `database.py`, not by manual
migrations.

Writes across layers are deduplicated by a composite key
(`date + date_buy + id + cost + installment`, or all columns except `created_at` for Raw) rather than by
a DB unique constraint — see `save_medallion_pipeline()` and `deduplicate_all_layers()` in
`database.py`.

### Categorization pipeline

`src/expenses/ai_categorizer.py` is a 2-step matcher, orchestrated by `repopulate_silver_layer()`:

1. **Local matching** (`match_merchants_with_history`) — checks unique Bronze merchant `id`s against (a)
   existing Silver `category`/`motivation` history in MySQL, then (b) keyword lists in
   the merged generic seed and machine-local dictionary (categories are dictionary keys, values
   are lists of matching substrings/motivations).
2. **Gemini AI fallback** (`batch_gemini_categorize_unmatched` → `gemini_categorize_unmatched`) — only
   merchants unmatched by step 1 are sent to Gemini, deduplicated and chunked (default batch size 25) to
   minimize API calls. The prompt template is `template/prompt.md` (Portuguese instructions), formatted
   with `data/categories.default.json` plus the optional `data/categories.local.json` contents. New
   `motivation` strings returned by Gemini are written only to the git-ignored local file, so future
   merchants increasingly resolve via step 1 without leaking learned merchant data into source control.

`src/gemini.py::gemini_category()` wraps the `google-genai` client with retry/backoff (503/429) and
fallback across a priority list of Gemini model names (in case the configured `GEMINI_MODEL` is
deprecated/unavailable).

Valid categories are the single source of truth in `src/expenses/config.py::CATEGORY_CONFIG` (label,
color, icon per category, e.g. `food`, `groceries`, `shopping`, ...). Any category string not in this
dict is coerced to `not_found` on load.

### Transaction semantics (important for analytics correctness)

`database.py::load_expenses_data()` derives several boolean/flag columns used throughout `analytics.py`
and the UI — don't recompute these ad hoc:

- `id` — normalized through `config.normalize_merchant_id()` on load: any merchant string matching a
  substring in `config.MERCHANT_ALIASES` is collapsed to that canonical name (the repository ships
  only fictional examples) so installment series aggregate as one merchant. Read-time only; Bronze/Silver
  are untouched. Edit the `MERCHANT_ALIASES` dict to add merchants — effect is immediate, no re-ingest.
- `is_payment` — true if `id` matches `PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS` (invoice
  settlement lines, not real spending — excluded from most KPIs/aggregations).
- `is_refund` — negative `cost` that is *not* a payment (a genuine merchant refund/estorno).
- `is_installment` — `total_installments > 1` or `installment > 0`.
- `year_month` / `buy_year_month`, `day_of_week`, `day` — derived from `date` / `date_buy` respectively.

Most functions in `analytics.py` follow the same pattern: filter out `is_payment` rows first (via the
shared `_exclude_payments` helper or an inline fallback regex when the flag column isn't present), then
aggregate. When adding a new analytics function, exclude payments the same way for consistency with
existing KPIs.

### UI structure

The dashboard answers one question — *how much did I spend, where, and what is already
committed?* — with the same layout in both frontends:

1. Header ("Despesas" + active period + last invoice date) and one row of filters: period
   (`data.PERIOD_LABELS`, resolved via `filters.resolve_default_months`), card holder, category.
   Other filter dimensions stay at `filters.DEFAULT_FILTERS` (net expenses).
2. Four KPIs from `kpi_cards`: spent in period, monthly average, last invoice vs previous,
   next-month installments vs `REFERENCE_BUDGET_LIMIT`. Future commitments use the holder/category
   scope but ignore the period.
3. Monthly evolution (bars + dashed 3M average), full width.
4. Category ranking | top 10 merchants (horizontal bars).
5. Future installments per month | largest purchases table.

Visual rules: **monochrome** — only `theme.ACCENT` (`#1F4E79`) and `theme.ACCENT_LIGHT` in figures
(tested), neutral greys for text/grid, no per-category colours, no red/green deltas (Streamlit
metrics use `delta_color="off"`). Fixed light theme (`.streamlit/config.toml` mirrors the tokens;
`assets/dashboard.css` mirrors them for Dash). UI text is pt-BR. Use `width="stretch"`, never the
deprecated `use_container_width`.

The Streamlit **Dados** page wraps the three data-operation modules in `ui/tabs/`
(`import_tab`, `categorize_tab`, `management`); they take a MySQL `engine` and write to
Raw/Bronze/Silver. Dash has no write paths.

`src/expenses/__init__.py` re-exports the public API of the `expenses` package (analytics, config,
database, parser, ai_categorizer, `filters.apply_filters`, `runtime` shims) — when adding a new function
meant to be used outside its module, add it there too.

The shared bronze-dedup ingest loop lives in `database.ingest_raw_bronze` (used by the import tab).

## Testing conventions

Tests are pure unit tests over DataFrame transforms (parser, analytics, `database._shape_silver_frame`
+ dedup key), `config.py` helpers (currency formatting, category mappings, `normalize_merchant_id`),
`filters.apply_filters` (`test_filters.py`), `ai_categorizer` matching / Gemini-response reshaping with
`gemini_category` stubbed (`test_categorizer.py`), the shared view model and figures
(`test_dashboard_data.py`), an import smoke for `main.py`, `dash_app.py` and the UI modules with the
DB entrypoints monkeypatched to raise (`test_app_imports.py`), a Streamlit render smoke
(`test_app_render.py`: `main.py` via `AppTest.from_file`, the Dados page via
`AppTest.from_function` because `st.navigation` callables can't be reached with `switch_page`) and
a Dash smoke (`test_dash_app.py`: layout ids + the pure `update_dashboard` callback body), all on
the synthetic `silver_history_df` fixture — no database or Gemini API calls are hit. Shared fixtures
(`sample_raw_csv_content`, `sample_csv_file`, `sample_expenses_df`, `silver_history_df`) live in
`tests/conftest.py`; extend these rather than duplicating sample data per
test file. The Silver enrichment lives in the pure `database._shape_silver_frame(df)` helper (called by
`load_expenses_data`), so test that instead of the DB-reading function.
