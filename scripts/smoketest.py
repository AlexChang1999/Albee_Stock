"""
Docker smoke test
=================
docker compose up 後跑這支腳本，快速確認後端 + 前端都真的活著、能互相打通。
只用標準函式庫（urllib），不吃 venv 依賴，容器內外都能跑。

用法：
    python scripts/smoketest.py
    python scripts/smoketest.py --backend http://localhost:8000 --frontend http://localhost:5173
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def _get(url: str, timeout: float = 5.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "albee-smoketest"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def _check(name: str, fn) -> bool:
    try:
        fn()
    except Exception as e:  # noqa: BLE001 — smoketest 就是要抓任何失敗原因
        print(f"[FAIL] {name}: {e}")
        return False
    print(f"[ OK ] {name}")
    return True


def _wait_for(url: str, retries: int, delay: float) -> None:
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            _get(url)
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(delay)
    raise TimeoutError(f"{url} 在等待時間內沒起來：{last_err}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--frontend", default="http://localhost:5173")
    parser.add_argument("--retries", type=int, default=24, help="等服務起來的重試次數")
    parser.add_argument("--delay", type=float, default=5.0, help="重試間隔秒數")
    args = parser.parse_args()

    print(f"等待後端 {args.backend} 就緒...")
    _wait_for(args.backend + "/", args.retries, args.delay)
    print(f"等待前端 {args.frontend} 就緒...")
    _wait_for(args.frontend + "/", args.retries, args.delay)

    results = []

    def check_root():
        status, body = _get(args.backend + "/")
        data = json.loads(body)
        assert status == 200, f"status={status}"
        assert "message" in data, f"回應缺 message 欄位：{data}"

    def check_status():
        status, body = _get(args.backend + "/status")
        data = json.loads(body)
        assert status == 200, f"status={status}"
        for key in ("is_paper", "allow_live", "live_armed"):
            assert key in data, f"回應缺 {key} 欄位：{data}"

    def check_docs():
        status, _ = _get(args.backend + "/docs")
        assert status == 200, f"status={status}"

    def check_strategies():
        status, body = _get(args.backend + "/strategies")
        data = json.loads(body)
        assert status == 200, f"status={status}"
        assert isinstance(data, list) and len(data) > 0, f"策略清單是空的：{data}"

    def check_frontend_html():
        status, body = _get(args.frontend + "/")
        assert status == 200, f"status={status}"
        html = body.decode("utf-8", errors="replace")
        assert 'id="root"' in html, "找不到前端 root 掛載點，可能沒吃到正確的 index.html"

    results.append(_check("後端根路徑 / 健康檢查", check_root))
    results.append(_check("後端 /status 環境旗標", check_status))
    results.append(_check("後端 /docs Swagger UI", check_docs))
    results.append(_check("後端 /strategies 策略清單", check_strategies))
    results.append(_check("前端首頁 HTML", check_frontend_html))

    if all(results):
        print("\n全部通過：後端 + 前端在 docker 裡都活著。")
        return 0
    print("\n有項目沒過，往上看 [FAIL] 訊息。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
