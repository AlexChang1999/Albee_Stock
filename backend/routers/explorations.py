"""
探討（檢討）檔案記憶 — 讀取 API（Phase 9 step-05）
=================================================
把 explorations/ 檔案記憶（LLM 事後檢討）開成可瀏覽的唯讀端點，給前端
「探討檢討頁」用。**唯讀**：只列路標、讀某篇內容；不寫 / 不改 / 不刪
（檢討由 chat/postmortem 產生）。

安全紅線：一律經 services.explorations 的函式讀檔——
  - 列表：list_index_entries()（解析 INDEX 路標）
  - 讀內容：read_exploration(name)（**已內建防路徑穿越**）
**不**自己 open() / 拼路徑。
"""

from fastapi import APIRouter, HTTPException

from backend.services import explorations

router = APIRouter(tags=["Explorations"])


@router.get("/explorations")
def list_explorations():
    """回探討路標清單（每筆 run_id / file / strategy / symbol / summary）。"""
    return explorations.list_index_entries()


@router.get("/explorations/{name}")
def get_exploration(name: str):
    """
    回某篇探討的完整 markdown 內容。
    讀取經 read_exploration 防穿越保護：非 .md / 目錄外 / 不存在 → 一律當找不到回 404。
    """
    content = explorations.read_exploration(name)
    if content is None:
        raise HTTPException(status_code=404, detail="找不到這篇探討")
    return {"name": name, "content": content}
