# 撰寫 Skill 的守則

> 本專案若要新增 Skill（放在 `.claude/skills/`），請遵守以下原則，
> 讓 AI 執行更穩、更省 Token。

## 1. 必寫「避坑指南 (Gotchas)」

Skill 中含金量最高的部分。把過去常犯的錯誤寫下來，能大幅提升成功率。

例：在交易相關 Skill 註明
- Alpaca 用 `alpaca-py` 不是 `alpaca-trade-api`
- Windows cp950 印中文會崩潰，需先 `sys.stdout.reconfigure(encoding="utf-8")`

## 2. 善用「漸進式揭露」（Progressive Disclosure）

不要把所有資訊塞進同一檔案。把範例、API 文件拆到子資料夾，
只在主檔告訴 Claude「這些檔案存在」，它需要時會自行讀取——省 Token 又精準。

```
.claude/skills/backtest/
├── SKILL.md          # 主檔：只寫流程 + 指到下面的檔
├── examples/         # 範例策略
└── reference/        # backtrader API 摘要
```

## 3. 賦予記憶能力

Skill 內部可讀寫 Log 或 JSON，讓 AI 查看自己昨天的操作紀錄、保持上下文連貫。

例：交易 Skill 把每次下單寫進 `logs/trades.jsonl`，下次先讀檔再決策。

## 4. 設計「按需觸發」的動態 Hook（危險操作攔截）

只在明確要碰正式環境（Prod）時才啟動的保護模式。

例：`/careful` 模式——切到 **Live Trading**（真錢）或執行 `DROP TABLE`、
`rm -rf` 前先攔截並要求二次確認。平時跑 Paper Trading 不啟動，不擋路。
