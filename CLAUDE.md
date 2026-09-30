# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Web app for ingesting, categorizing (via Google Gemini AI), and analyzing personal credit card
expenses, backed by a MySQL **Medallion Architecture** (Raw → Bronze → Silver). Package/dependency
management is via `uv`.

**Layout — uv workspace.** The root `pyproject.toml` is the workspace root *and* the shared,
framework-free backend package `expenses` (`src/expenses/`: config, database, parser, analytics,
filters, ai_categorizer, gemini, runtime) plus `data/` and `template/`. Each frontend is a workspace
member under `app/` with its **own `pyproject.toml` (only its dependencies), `src/` package,
`tests/`, `main.py` entrypoint and `Dockerfile`**:

```
app/streamlit/  pyproject.toml (expenses-streamlit) · Dockerfile · main.py · .streamlit/config.toml
                src/expenses_streamlit/  app.py (main()), charts, figures, insights, styles, sidebar, tabs/
                tests/
app/dash/       pyproject.toml (expenses-dash) · Dockerfile · main.py
                src/expenses_dash/  __init__ (create_app), analyses, callbacks, data, figures, fmt,
                                    layout, pages, theme, assets/dashboard.css
                tests/
```

- Imports: `expenses.*` (backend), `expenses_streamlit.*`, `expenses_dash.*` — real installed
  packages (editable), no `sys.path` tricks. Apps depend on `expenses` via
  `[tool.uv.sources] expenses = { workspace = true }`. The apps never import each other and the
  backend imports neither Streamlit nor Dash (`tests/test_architecture.py`).
- A new dependency goes into the pyproject of the package that imports it (backend deps in the
  root, `streamlit` only in `app/streamlit`, `dash` only in `app/dash`), then `uv lock`.
- `app/streamlit/main.py` is just `from expenses_streamlit.app import main; main()`. `app.py`
  reaches the DB through the `database` module (`database.get_db_engine()`), not imported names,
  so tests can stub it after the module is cached.
- Each app runs **from its own folder** (Streamlit only reads `.streamlit/config.toml` from the
  current directory), so project files are resolved from `config.PROJECT_ROOT`, never the cwd:
  `CATEGORY_SEED_PATH`, `CATEGORY_LOCAL_PATH` (relative values are taken from the repo root) and
  `PROMPT_TEMPLATE_PATH`. Keep new file paths anchored the same way. Dash assets ship inside the
  package (`expenses_dash.ASSETS_DIR`).

**Streamlit** (`app/streamlit/`, port `8503`) consumes `analytics.py` + `config.py` +
`filters.apply_filters` and the framework-agnostic `charts.py` (theme/hide-amounts via
`chart_context`), `figures.py` (figure builders) and `insights.py` (`Insight` cards). **Add new
charts/insights to `figures.py` / `insights.py`, not inline in a tab.** `charts.py`, `figures.py`,
`insights.py` must not import Streamlit at module level.

**Dash** (`app/dash/`, port `DASH_PORT` = `8050`) is a read-only dashboard; see *Dash frontend* below.

The former Streamlit coupling in `database.py` / `parser.py` / `ai_categorizer.py` lives behind
`expenses.runtime` (`cache_data`, `cache_resource`, `clear_caches`, `notify_error`,
`notify_warning`) — **never re-add `import streamlit` to those three modules** (the pure-Python
test suite imports them with no Streamlit runtime).

## Commands

```bash
# Install dependencies (including dev group)
uv sync --all-packages --all-groups

# Run the Streamlit app (port 8503) — from its folder so .streamlit/config.toml applies
uv run --directory app/streamlit streamlit run main.py

# Run the Dash dashboard (port 8050, from .env DASH_PORT)
uv run --directory app/dash python main.py

# Run all tests
uv run pytest

# Run a single test file / test
uv run pytest tests/test_analytics.py
uv run pytest tests/test_analytics.py::test_calculate_kpis_basic
uv run pytest app/dash/tests            # one app's suite
uv run pytest --cov=expenses --cov=expenses_streamlit --cov=expenses_dash

# Lint + format (both enforced in CI)
uv run ruff check .
uv run ruff format .            # CI runs `ruff format --check .`

# Docker Compose (`streamlit` = :8503, `dash` = :8050, same image)
docker compose up --build -d
docker compose logs -f streamlit dash
# After renaming/removing a service, drop the old fixed-name container once:
docker compose down --remove-orphans
```

CI (`.github/workflows/ci.yml`) runs on **every branch push**, **every PR**, and manual dispatch
(per-ref `concurrency` cancels superseded runs): `uv sync --all-packages --all-groups --locked` (fails on
`pyproject`/`uv.lock` drift, matching the Dockerfiles' `--frozen`), `uv run ruff check .`,
`uv run ruff format --check .`, then `uv run pytest` with coverage for the three packages.

Environment variables live in `.env` (see `.env.example`): `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`,
`MYSQL_PASSWORD`, `MYSQL_TABLE` (unified table name across all three DBs), `MYSQL_DB_RAW`,
`MYSQL_DB_BRONZE`, `MYSQL_DB_SILVER`, `GEMINI_API_KEY`, `GEMINI_MODEL`,
`REFERENCE_BUDGET_LIMIT`, `CATEGORY_LOCAL_PATH`, `STREAMLIT_PORT` / `DASH_PORT` (host ports in
`docker-compose.yml`; `DASH_PORT` is also read by `expenses.config`).
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
a DB unique constraint — see `ingest_raw_bronze()` (Bronze key via `_bronze_row_key`, which
normalizes dates / DECIMALs so rows read back from MySQL match freshly parsed ones),
`repopulate_silver_layer()` and `deduplicate_all_layers()`.

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

`expenses.gemini.gemini_category()` wraps the `google-genai` client with retry/backoff (503/429) and
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

`expenses_streamlit.app.main()` wires global sidebar filters (`sidebar.py`) applied to a `df_full` loaded from
Silver, producing `df_filtered`, then renders 6 top-level tabs from `tabs/` — five
analytic tabs, each answering **one question**, then a **Data** tab that nests the three write paths:

| Tab (module) | Question | Content |
|---|---|---|
| Overview (`dashboard`) | How much did I spend and where? | 4 KPIs (net, monthly avg, latest invoice, next-month installments vs `REFERENCE_BUDGET_LIMIT`), "Needs attention" strip, monthly total + 3M average, category + top-merchant bars |
| Trends (`trends`) | Is spending changing? | 4 KPIs, one comparison chart (previous period / last year), momentum in an expander |
| Watchlist (`watchlist`) | What needs my attention? | Recurring charges, unusual purchases, uncategorized spending; frequency changes in an expander |
| Categories (`category`) | What is inside one category? | 4 KPIs (total delta = 3M momentum), history, top merchants; day-of-week and largest transactions in expanders |
| Reports (`reports`) | What is committed ahead / give me the data | Installment commitments vs limit, invoice totals, all rows, CSV |
| Data → Ingest / Categorize / Manage (`import_tab`, `categorize_tab`, `management`) | — | Write paths into Raw/Bronze/Silver |

Layout rules for analytic tabs (keep them when adding content): no emojis in labels, headings or
buttons; **at most one row of ≤4 `st.metric(..., border=True)`** with explanations in `help=`,
charts in `st.container(border=True)` (max two per row), secondary tables in collapsed
`st.expander`s, headings via `styles.section()`. Insight cards are reserved for things that need
action: `insights.attention_insights()` keeps only `critical`/`warning` (max 3) for the Overview
strip; "all good" is a quiet caption, and cards show no icon (severity color only). Every chart value
axis is money: `charts.apply_chart_theme` sets `R$` ticks and no axis title. Use `width="stretch"`, never the deprecated `use_container_width`.

Each tab module exposes a single `render_*_tab(...)` function imported via
`expenses_streamlit/tabs/__init__.py`. Most tabs take `(df_filtered, df_full)`; ingestion/categorization/
management tabs take a MySQL `engine` instead (or in addition) since they write data rather than just
visualize it.

`src/expenses/__init__.py` re-exports the public API of the `expenses` package (analytics, config,
database, parser, ai_categorizer, `filters.apply_filters`, `runtime` shims) — when adding a new function
meant to be used outside its module, add it there too.

The shared bronze-dedup ingest loop lives in `database.ingest_raw_bronze` (used by the import tab).

The sidebar keeps only Period, Cardholder and Categories visible (empty selection = all; the
Invoices picker appears only for the "Custom" period). Transaction type / payment method / merchant
search live in "More filters"; a "Display" expander holds:
- **Hide amounts** (`st.toggle`, `key="hide_amounts"`) — `main.py` reads the session-state flag and
  calls `styles.render_amount_visibility_css()`, which injects CSS that blurs `stMetricValue` /
  `stMetricDelta` / `.insight-card-message` / `.hide-amount` (hover reveals). No change to the individual
  `st.metric` call sites.
- **Reload data** — `runtime.clear_caches()` + rerun.

The theme is fixed dark in `app/streamlit/.streamlit/config.toml` (same palette as the Dash app; toolbar in
`viewer` mode). `charts.py` still derives grid / tick colors from `st.get_option("theme.base")`.

### Dash frontend

`expenses_dash` (`app/dash/`) is a read-only app (writes stay in the Streamlit **Data** tab). Header +
three global filters (period, holders, categories) sit above six `dcc.Tabs`, covering the
Streamlit analyses plus a few Dash-only ones, all in pt-BR:

| Tab | View model | Content |
|---|---|---|
| Visão geral | `data.build_view` | 4 KPIs, monthly total + 3M avg, category / top-merchant bars, future installments, largest purchases |
| Tendências | `analyses.trends_view` | trend / 3M avg / projection / period-vs-previous KPIs, category comparison, category × month heatmap, same months last year, momentum table |
| Hábitos | `analyses.habits_view` | purchases/month, ticket (mean + median), installment share, merchant concentration (top 10 + Pareto 80%); single vs installment per month, ticket-size bands, weekday, per cardholder |
| Atenção | `analyses.watchlist_view` | fixed cost, recurring charges, outliers, uncategorized, merchants new in the period, frequency shifts (tables only) |
| Categorias | `analyses.category_view` | own category picker (options follow the filters), KPIs, monthly history, merchants, largest purchases |
| Relatórios | `analyses.reports_view` | installments vs `REFERENCE_BUDGET_LIMIT`, upcoming installments, invoice totals, CSV download (`export_frame`) |

- Every view model starts from `data.slice_data(df_full, period, holders, categories)`:
  `df` = selected period/holders/categories (payments removed), `df_scope` = same holders/categories
  over the full history (installment projections, recurring charges and comparisons need it).
  **Add numbers to the view models, never in callbacks or pages;** only call `analytics.py`.
- `fmt.py` — pt-BR presentation: `brl()` (`R$ 1.234,56`), `pct()`, `integer()`, Portuguese category
  names (`CATEGORY_LABELS_PT`, applied to `category_label` inside `slice_data`, so every tab gets
  them) and weekday names. **Use these in the Dash app, not `config.format_currency_br`** (which
  keeps the Streamlit app's `R$ 1,234.56`). Plotly uses `separators=",."` for the same format.
- KPI dicts are `{label, value, note, help, tone}`; `tone` in `bad`/`good`/`neutral` colours the
  note (`data.spend_delta` makes rising spend `bad`, falling `good`).
- `figures.py` — Plotly builders; `theme.py` — dark tokens, `plotly_layout()`, `LEGEND_TOP`.
  Category marks use `config.CATEGORY_CONFIG` colors; series use `ACCENT` / `AVERAGE` /
  `COMMITMENT` / `PREVIOUS` / `LIMIT`. Figures may only use `theme.PALETTE` (tested).
- `layout.py` — static structure + shared components (`card`, `kpi_row`, `row`, `graph`, generic
  `table(df, [(header, column, kind)])`); `pages.py` — body of each secondary tab.
- `callbacks.py` — Overview fills fixed ids (`update_dashboard`); each other tab has one callback
  that returns `no_update` unless its tab is active (`render_tab`, `render_category` are the pure,
  tested bodies); CSV via `dcc.Download`.
- `create_app(loader=None)` in `__init__.py`; `loader` defaults to `load_expenses_data` (imported
  lazily). `app.layout` is a function so filter options refresh on page load.
- Styles: `expenses_dash/assets/dashboard.css` (dark theme; overrides Dash 4's `--Dash-*` variables
  for dropdowns and styles `dcc.Tabs` via `pe-tab*` classes). The package must not import
  Streamlit (tested).

## Testing conventions

One suite per package, all run by a plain `uv run pytest` (`testpaths` in the root pyproject,
`--import-mode=importlib` because file names repeat across suites):

- `tests/` — backend: parser, analytics, `database._shape_silver_frame` + dedup key, DB write paths
  against **SQLite** engines (`test_database_writes.py`: `ingest_raw_bronze`,
  `deduplicate_all_layers`, `ensure_databases_exist` with a fake engine), `config` helpers,
  `filters`, `ai_categorizer` with `gemini_category` stubbed, `runtime` caches; plus
  `test_architecture.py` (package boundaries, app folder layout) and
  **`test_every_function_is_tested.py`**, which fails when any module-level function in
  `src/expenses` or `app/*/src` is not named in some test. Add a test when it fails.
- `app/streamlit/tests/` — figures, charts, insights, styles, tab helpers, each render function via
  `AppTest.from_function` (`test_render_tabs.py`, `test_styles.py`), the full app via
  `AppTest.from_file("main.py")` (`test_app_render.py`) and import smoke.
- `app/dash/tests/` — fmt, view models (`test_data.py`, `test_analyses.py`), figures, layout
  components, pages, callbacks (`test_app.py`: `create_app`, `register_callbacks`,
  `update_dashboard`) and import smoke; component helpers in `app/dash/tests/conftest.py`.

No test touches MySQL or the Gemini API. Shared fixtures (`sample_raw_csv_content`,
`sample_csv_file`, `sample_expenses_df`, `silver_history_df`, `no_db`) live in the **root
`conftest.py`**; extend these rather than duplicating sample data per test file. The Silver
enrichment lives in the pure `database._shape_silver_frame(df)` helper (called by
`load_expenses_data`), so test that instead of the DB-reading function.
