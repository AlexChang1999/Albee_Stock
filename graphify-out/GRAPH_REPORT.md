# Graph Report - .  (2026-06-12)

## Corpus Check
- Corpus is ~310 words - fits in a single context window. You may not need a graph.

## Summary
- 17 nodes · 16 edges · 4 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 57,454 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_資料搬遷與零改切換|資料搬遷與零改切換]]
- [[_COMMUNITY_文件與 Runbook|文件與 Runbook]]
- [[_COMMUNITY_Neon PostgreSQL 環境|Neon PostgreSQL 環境]]
- [[_COMMUNITY_Alembic 種子列踩坑|Alembic 種子列踩坑]]

## God Nodes (most connected - your core abstractions)
1. `PostgreSQL 17` - 4 edges
2. `2026-06-12 Neon Postgres 搬遷實錄` - 4 edges
3. `migrate_once.py` - 3 edges
4. `seed-row PK collision` - 3 edges
5. `Neon` - 2 edges
6. `SQLite (albee_stock.db)` - 2 edges
7. `DATABASE_URL` - 2 edges
8. `Alembic` - 2 edges
9. `反 FK 順序清空 + 正 FK 順序插入（單一交易）` - 2 edges
10. `backend/config.py` - 1 edges

## Surprising Connections (you probably didn't know these)
- `explorations/INDEX.md（探討路標索引）` --references--> `2026-06-12 Neon Postgres 搬遷實錄`  [EXTRACTED]
  explorations/INDEX.md → explorations/2026-06-12-neon-postgres-setup.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **SQLite → Neon 搬遷流程（備份→建 schema→搬資料→驗證）** — explorations_2026_06_12_neon_postgres_setup_sqlite, explorations_2026_06_12_neon_postgres_setup_alembic, explorations_2026_06_12_neon_postgres_setup_migrate_once_py, explorations_2026_06_12_neon_postgres_setup_postgresql, explorations_2026_06_12_neon_postgres_setup_neon [EXTRACTED 1.00]
- **DATABASE_URL 驅動的零程式碼資料庫切換** — explorations_2026_06_12_neon_postgres_setup_config_py, explorations_2026_06_12_neon_postgres_setup_database_url, explorations_2026_06_12_neon_postgres_setup_sqlite, explorations_2026_06_12_neon_postgres_setup_postgresql [EXTRACTED 1.00]

## Communities (4 total, 0 thin omitted)

### Community 0 - "資料搬遷與零改切換"
Cohesion: 0.40
Nodes (5): backend/config.py, DATABASE_URL, migrate_once.py, 反 FK 順序清空 + 正 FK 順序插入（單一交易）, SQLite (albee_stock.db)

### Community 1 - "文件與 Runbook"
Cohesion: 0.40
Nodes (5): 2026-06-12 Neon Postgres 搬遷實錄, docs/guides/home-boot-checklist.md, PowerShell 內嵌 python -c 引號逃逸坑, docs/guides/setup-postgres-sync.md, explorations/INDEX.md（探討路標索引）

### Community 2 - "Neon PostgreSQL 環境"
Cohesion: 0.50
Nodes (4): Neon auto-suspend 冷啟動, Neon, PostgreSQL 17, psycopg2-binary

### Community 3 - "Alembic 種子列踩坑"
Cohesion: 0.67
Nodes (3): Alembic, automation_config（單列設定表）, seed-row PK collision

## Knowledge Gaps
- **6 isolated node(s):** `backend/config.py`, `automation_config（單列設定表）`, `docs/guides/setup-postgres-sync.md`, `docs/guides/home-boot-checklist.md`, `psycopg2-binary` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PostgreSQL 17` connect `Neon PostgreSQL 環境` to `資料搬遷與零改切換`, `Alembic 種子列踩坑`?**
  _High betweenness centrality (0.250) - this node is a cross-community bridge._
- **Why does `migrate_once.py` connect `資料搬遷與零改切換` to `Neon PostgreSQL 環境`?**
  _High betweenness centrality (0.233) - this node is a cross-community bridge._
- **What connects `backend/config.py`, `PowerShell 內嵌 python -c 引號逃逸坑`, `automation_config（單列設定表）` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._