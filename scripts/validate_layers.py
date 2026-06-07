"""
層驗證報表 CLI（Phase 7 收尾）
================================
一鍵跑「用 step-07 驗證 step-03~06 各層有沒有加分」，印出每層的 verdict 表。

用法（專案根目錄）：
    venv\\Scripts\\python.exe scripts/validate_layers.py                # 跑 watchlist 全部
    venv\\Scripts\\python.exe scripts/validate_layers.py AAPL MSFT NVDA  # 跑指定標的
    venv\\Scripts\\python.exe scripts/validate_layers.py --source alpaca # 換資料源（預設 yfinance）

讀法：worth=True 代表「加這層在 OOS 上贏過不加 → 留」；worth=False（improvement≤0 或 fold 不足）
代表「沒加分 → 該砍/降級」。step-04 比的是終值報酬（凱利是部位大小）；step-06 誠實標記不可驗證。
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.layer_validation import validate_layers


def _parse_args(argv):
    """極簡解析：--source X 設資料源，其餘當標的代號。"""
    source, symbols = "yfinance", []
    i = 0
    while i < len(argv):
        if argv[i] == "--source" and i + 1 < len(argv):
            source = argv[i + 1]
            i += 2
        else:
            symbols.append(argv[i].upper())
            i += 1
    return source, (symbols or None)


def _row(layer: str, v: dict) -> str:
    if v.get("worth") is None:
        return f"  {layer:<26} {'N/A':>6}  {v.get('reason', '')}"
    return (f"  {layer:<26} {str(v['worth']):>6}  "
            f"folds={v['folds']:<3} base={v['baseline_mean']:<10} "
            f"cand={v['candidate_mean']:<10} Δ={v['improvement']:<10}  {v['reason']}")


def main():
    source, symbols = _parse_args(sys.argv[1:])
    print(f"\n=== 層驗證報表（source={source}）===")
    print("抓資料 + 跑 walk-forward 回測，請稍候…\n")

    out = validate_layers(symbols=symbols, source=source)

    print(f"納入標的（{len(out['symbols'])}）：{', '.join(out['symbols']) or '（無）'}")
    if out["skipped"]:
        print(f"略過（{len(out['skipped'])}）：" +
              ", ".join(f"{s['symbol']}({s['reason']})" for s in out["skipped"]))
    print()
    print("層                          worth   明細")
    print("-" * 100)
    for key in ("adaptive", "meta", "kelly"):
        print(_row(out[key]["layer"], out[key]["verdict"]))
    print(_row(out["event"]["layer"], out["event"]["verdict"]))
    print("-" * 100)
    print("\n判讀：worth=True 留、False 該砍/降級；step-04 比終值報酬；step-06 不可 OOS 驗證（風險煞車）。")


if __name__ == "__main__":
    main()
