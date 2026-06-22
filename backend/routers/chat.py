"""
LLM 思考助手 API ── Phase 5（OpenAI 相容介面，預設接本機 Ollama）
================================================
這支 router 負責「思考」：制定策略、調參建議、事後檢討。實際的「做事」
（跑回測、下單）一律走 Python，助手完全碰不到。

為什麼用 OpenAI 相容介面？
- 同一套程式可接很多家供應商：本機 Ollama（免費）、Gemini 免費層、Groq…
- 換供應商只改 .env 的 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL，程式不動。

為什麼不用「工具呼叫（tool use）」？
- 改成「把回測歷史等記憶**預先注入** system 提示」。小型/本機模型對 tool calling
  支援不穩，預先注入更可靠也更簡單；功能一樣（讀歷史、分析 EV、給建議）。

鐵則（絕不違反）：
- 助手不能下單、不能啟停 Bot、不能跑回測、不能碰實盤安全閥、不能執行系統指令。
  它根本沒有這些能力（沒有任何會改動的工具/端點）。跑回測請使用者按介面「跑回測」（Python 做）。
- 判斷策略好壞看「期望值 EV」，不是只看勝率。全程先 Paper 驗證，慎防過度擬合。
"""

import json
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.database import SessionLocal
from backend.models import StrategyPreset, BacktestRun, Bot, DecisionLog
from backend.strategies import STRATEGY_REGISTRY
from backend.services import explorations

router = APIRouter(tags=["Chat"])

_MAX_TOKENS = 1024
_TOP_RUNS = 10            # 注入給模型的回測歷史筆數上限（依 EV 取前 N，避免 prompt 過長）
_TIMEOUT_SEC = 120        # 本機 CPU 生成可能較慢，逾時給寬一點
_MAX_PICK = 3             # 事後檢討時，最多挑幾篇過去探討來參考
_MAX_SELECT_TOKENS = 200  # 「挑檔」那一段只需回短短的檔名清單
_MAX_REF_CHARS = 6000     # 注入的過去探討總字數上限（避免本機模型 prompt 爆）
_LESSON_DECISIONS = 60    # 讀教訓時注入的決策史筆數上限（取最近 N 筆）

# 可用策略鍵（放進 system 提示，讓助手草擬策略時用對的代號）
_STRATEGY_KEYS = ", ".join(STRATEGY_REGISTRY.keys())

# 視為「本機」的主機名（資料不離開這台電腦）
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _is_local_llm() -> bool:
    """LLM_BASE_URL 是否指向本機。空字串/解析不出 host 時，保守當作非本機。"""
    host = (urlparse(settings.LLM_BASE_URL).hostname or "").lower()
    return host in _LOCAL_HOSTS


def _cloud_blocked() -> bool:
    """指向外部雲端、卻沒開外送閘 → 擋下（隱私安全閥）。"""
    return (not _is_local_llm()) and (not settings.LLM_ALLOW_CLOUD)


_CLOUD_BLOCKED_DETAIL = (
    "LLM_BASE_URL 指向外部服務，助手會把『策略方案/回測歷史/探討筆記』送到第三方。"
    "預設只允許本機（localhost）。確定要用雲端供應商，請在後端 .env 設 "
    "LLM_ALLOW_CLOUD=true（等於同意資料外送），或把 LLM_BASE_URL 改回本機 Ollama。"
)


def _get_client():
    """
    建立 OpenAI 相容 client；沒設定 base_url/model 就回 None（呼叫端據此回 400）。
    max_retries=0：連不上時快速失敗，把錯誤如實回給使用者，而不是悶著重試。
    """
    if not settings.LLM_BASE_URL or not settings.LLM_MODEL:
        return None
    from openai import OpenAI
    return OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY or "not-needed",  # 有些供應商（如 Ollama）不檢查金鑰
        timeout=_TIMEOUT_SEC,
        max_retries=0,
    )


def _build_memory_context() -> str:
    """
    把「目前系統的即時資料」整理成一段文字，注入 system 提示當助手的記憶：
    環境狀態 + 策略方案 + 回測歷史（依 EV 排序、含既有檢討）。
    這就是助手「越看越聰明」的來源——讀得到過去的回測與檢討。
    """
    db = SessionLocal()
    try:
        live_armed = (not settings.IS_PAPER) and settings.ALLOW_LIVE_TRADING
        status = f"模擬環境={settings.IS_PAPER}；實盤武裝={live_armed}"

        presets = db.query(StrategyPreset).all()
        preset_lines = [
            f"- #{p.id} {p.name}｜{p.strategy_key}｜{p.symbol}｜"
            f"參數{json.dumps(p.params or {}, ensure_ascii=False)}"
            f"{'｜★收藏' if p.is_favorite else ''}"
            for p in presets
        ] or ["（無）"]

        runs = db.query(BacktestRun).all()
        runs.sort(
            key=lambda r: (r.metrics or {}).get("expected_value", float("-inf")),
            reverse=True,
        )
        run_lines = []
        for r in runs[:_TOP_RUNS]:
            m = r.metrics or {}
            pm = f"｜檢討:{r.claude_postmortem}" if r.claude_postmortem else ""
            run_lines.append(
                f"- #{r.id} {r.strategy_key}/{r.symbol}｜EV={m.get('expected_value')}｜"
                f"PF={m.get('profit_factor')}｜勝率={m.get('win_rate_pct')}%｜"
                f"報酬={m.get('total_return_pct')}%｜回撤={m.get('max_drawdown_pct')}%{pm}"
            )
        run_block = "\n".join(run_lines) or "（無）"
        more = (
            f"（共 {len(runs)} 筆，僅列 EV 前 {_TOP_RUNS}）"
            if len(runs) > _TOP_RUNS else ""
        )

        base = (
            f"【目前環境】{status}\n"
            f"【策略方案】\n" + "\n".join(preset_lines) + "\n"
            f"【回測歷史·依 EV 排序{more}】\n" + run_block
        )
        # 附上「探討路標」：讓一般對話也知道有哪些過去檢討可參考
        signpost = explorations.read_index().strip()
        if signpost:
            if len(signpost) > 1500:
                signpost = signpost[:1500] + "…"
            base += "\n\n【探討路標（過去檢討清單）】\n" + signpost
        return base
    finally:
        db.close()


def _system_text() -> str:
    """組 system 提示：角色 + 鐵則 + 即時記憶。"""
    return (
        "你是 Albee Stock 美股交易系統的「策略思考助手」。你只負責「思考」，不負責「做事」。\n\n"
        "職責：設計交易策略、建議參數微調、對回測結果做事後檢討。\n"
        "判斷策略好壞**看期望值 EV（每筆平均盈虧），不是只看勝率**；"
        "高勝率但 EV 為負（常是小賺多次、一次大賠）很危險，要明確點出。\n\n"
        "鐵則（絕不違反）：你不能下單、不能啟停 Bot、不能跑回測、不能碰實盤安全閥、"
        "不能執行系統指令——你沒有這些能力，別假裝做得到。跑回測請使用者按介面上的"
        "「跑回測」按鈕（那是 Python 做的）。全程先 Paper 驗證，慎防過度擬合。\n"
        f"可用的策略代號只有：{_STRATEGY_KEYS}。草擬策略時請用這些代號。\n\n"
        "以下是目前系統的即時資料，回答時請參考：\n"
        f"{_build_memory_context()}\n\n"
        "回答用繁體中文，簡潔、具體、可執行。"
    )


def _complete(client, messages: list, max_tokens: int = _MAX_TOKENS) -> str:
    """呼叫 LLM，回傳純文字回覆。"""
    resp = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return (resp.choices[0].message.content or "").strip()


def _friendly_err(e: Exception) -> str:
    """把底層錯誤轉成新手看得懂的提示（特別是連不上 Ollama 的情況）。"""
    msg = str(e)
    low = msg.lower()
    if "connect" in low or "refused" in low or "connection" in low:
        return (
            "連不上 LLM 服務。若用預設的本機 Ollama：請先安裝並啟動（執行 `ollama serve`），"
            f"且已下載模型（`ollama pull {settings.LLM_MODEL}`）。"
            "或在後端 .env 改 LLM_BASE_URL 接其他供應商。\n"
            f"（原始錯誤：{msg}）"
        )
    return f"LLM 呼叫失敗：{msg}"


# ============================================================
# 事後檢討的「兩段式」輔助：先挑相關過去探討，再讀內容
# ============================================================
def _parse_filename_list(raw: str) -> list[str]:
    """從模型回覆裡穩健抓出 JSON 字串陣列（檔名清單）。抓不到回空清單。"""
    if not raw:
        return []
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(raw[start : end + 1])
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if isinstance(x, str)]


def _select_references(client, run, entries: list) -> list[str]:
    """
    兩段式第一步：請模型從路標清單挑相關的過去探討檔名。
    挑檔失敗（解析不出/全無效）→ 回退用 metadata 規則挑（同策略優先、再取最近）。
    """
    if not entries:
        return []
    signpost = explorations.read_index().strip()
    m = run.metrics or {}
    sel_sys = "你是檔案挑選器。只回 JSON 字串陣列，不要任何多餘文字。"
    sel_user = (
        f"這次回測：策略 {run.strategy_key}、標的 {run.symbol}、"
        f"EV {m.get('expected_value')}、勝率 {m.get('win_rate_pct')}%。\n"
        f"以下是過去探討的路標清單：\n{signpost}\n\n"
        f"挑出最多 {_MAX_PICK} 個和這次最相關（可借鏡）的檔名，"
        '只回 JSON 字串陣列，例如 ["run-0007-rsi-aapl.md"]。沒有相關就回 []。'
    )
    try:
        raw = _complete(
            client,
            [{"role": "system", "content": sel_sys},
             {"role": "user", "content": sel_user}],
            max_tokens=_MAX_SELECT_TOKENS,
        )
        picked = _parse_filename_list(raw)
    except Exception:
        picked = []
    # 只保留真實存在的檔（順便擋掉模型亂編的檔名）
    picked = [f for f in picked if explorations.read_exploration(f) is not None]
    if not picked:
        picked = explorations.select_candidates_by_meta(run, entries, _MAX_PICK)
    return picked[:_MAX_PICK]


def _read_reference_blocks(refs: list[str]) -> str:
    """把被挑中的過去探討內容讀出來、串成一段（總字數設上限）。"""
    if not refs:
        return "（無相關過去探討）"
    blocks, total = [], 0
    for f in refs:
        content = explorations.read_exploration(f) or ""
        remain = _MAX_REF_CHARS - total
        if remain <= 0:
            break
        if len(content) > remain:
            content = content[:remain] + "…"
        blocks.append(f"### 過去探討：{f}\n{content}")
        total += len(content)
    return "\n\n".join(blocks) if blocks else "（無相關過去探討）"


# ============================================================
# API 端點
# ============================================================
class ChatMessage(BaseModel):
    role: str       # 'user' 或 'assistant'
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = []


class PostmortemRequest(BaseModel):
    run_id: int


_NO_LLM_DETAIL = "未設定 LLM（LLM_BASE_URL / LLM_MODEL）。請檢查後端 .env。"


@router.post("/chat")
def chat(payload: ChatRequest):
    """與思考助手對話（無狀態，前端送完整 messages）。"""
    client = _get_client()
    if client is None:
        raise HTTPException(status_code=400, detail=_NO_LLM_DETAIL)
    if _cloud_blocked():
        raise HTTPException(status_code=400, detail=_CLOUD_BLOCKED_DETAIL)

    convo = [{"role": m.role, "content": m.content} for m in payload.messages]
    if not convo:
        raise HTTPException(status_code=400, detail="messages 不能為空")

    messages = [{"role": "system", "content": _system_text()}, *convo]
    try:
        reply = _complete(client, messages)
    except Exception as e:
        raise HTTPException(status_code=400, detail=_friendly_err(e))
    return {"reply": reply, "stub": False}


@router.post("/chat/postmortem")
def postmortem(payload: PostmortemRequest):
    """
    請助手以 EV 角度檢討某筆回測，並把結果存回該紀錄（claude_postmortem 欄位）。
    存起來後，之後 _build_memory_context 讀得到 → 助手會越來越聰明。
    （欄位沿用 claude_postmortem 這個名字，內容其實是「目前所接 LLM」的分析。）
    """
    client = _get_client()
    if client is None:
        raise HTTPException(status_code=400, detail=_NO_LLM_DETAIL)
    if _cloud_blocked():
        raise HTTPException(status_code=400, detail=_CLOUD_BLOCKED_DETAIL)

    db = SessionLocal()
    try:
        run = db.query(BacktestRun).filter(BacktestRun.id == payload.run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail=f"找不到回測紀錄 #{payload.run_id}")

        # 第一步：挑出相關的過去探討（LLM 挑，失敗自動回退；首次無歷史則略過）
        explorations.ensure_dir()
        entries = [
            e for e in explorations.list_index_entries() if e["run_id"] != run.id
        ]
        refs = _select_references(client, run, entries)
        ref_text = _read_reference_blocks(refs)

        m = run.metrics or {}
        sys_text = (
            "你是交易策略檢討助手，一律以「期望值 EV」角度分析策略好壞。"
            "回答用繁體中文，簡潔具體、可執行。"
        )
        prompt = (
            "請以「期望值 EV」角度檢討這次回測，指出『錯在哪、怎麼改』。\n\n"
            f"策略：{run.strategy_key}　標的：{run.symbol}　"
            f"參數：{json.dumps(run.params or {}, ensure_ascii=False)}\n"
            f"期望值 EV/筆：{m.get('expected_value')}　獲利因子 PF：{m.get('profit_factor')}\n"
            f"勝率：{m.get('win_rate_pct')}%　敗率：{m.get('loss_rate_pct')}%　"
            f"平均賺：{m.get('avg_win')}　平均賠：{m.get('avg_loss')}\n"
            f"總報酬：{m.get('total_return_pct')}%　最大回撤：{m.get('max_drawdown_pct')}%　"
            f"完整買賣：{m.get('num_round_trips')} 筆\n\n"
            f"參考以下過去探討，避免重蹈覆轍（可借鏡，也可指出與這次的不同）：\n{ref_text}\n\n"
            "請給：①一句話總評（EV 正負代表什麼）②最可能的問題 ③1~2 個具體調整方向。"
        )
        # 第二步：寫新檢討
        try:
            analysis = _complete(client, [
                {"role": "system", "content": sys_text},
                {"role": "user", "content": prompt},
            ])
        except Exception as e:
            raise HTTPException(status_code=400, detail=_friendly_err(e))

        # 寫成探討檔 + 更新路標索引；DB 也存一份供前端標「已檢討」
        explorations.write_exploration(run, analysis, references=refs)
        run.claude_postmortem = analysis
        db.commit()
        return {"run_id": run.id, "postmortem": analysis, "references": refs, "stub": False}
    finally:
        db.close()


class BotLessonsRequest(BaseModel):
    bot_id: int


def _format_decision_history(decisions: list) -> str:
    """把決策史（時間倒序撈來）排成「時間正序、一行一筆」的可讀表，注入 LLM。

    每行：時間｜動作/訊號｜價｜量｜股數｜指標快照｜原因。
    含「沒成交但有決策」的觀望/跳過——教訓常藏在「沒進場」與「為何沒進」裡。
    """
    lines = []
    for d in reversed(decisions):  # 撈的是 desc，反轉成正序讀起來才順
        t = d.created_at.strftime("%m-%d %H:%M") if d.created_at else "—"
        price = f"${d.price:.2f}" if d.price is not None else "—"
        vol = f"{int(d.volume):,}" if d.volume is not None else "—"
        qty = f"{d.qty:g}股" if d.qty is not None else "—"
        inds = json.dumps(d.indicators, ensure_ascii=False) if d.indicators else "—"
        lines.append(
            f"{t}｜{d.action}/{d.signal}｜價{price}｜量{vol}｜{qty}｜指標{inds}｜{d.reason or ''}"
        )
    return "\n".join(lines)


@router.post("/chat/bot-lessons")
def bot_lessons(payload: BotLessonsRequest):
    """讀某 Bot 的決策史，請本機 LLM 產一段「教訓摘要」（為何在那些點買/賣/沒動，下次怎麼改）。

    資料源用 DecisionLog（Phase 15 起含 量/股數/指標快照）——它是成交與觀望的超集，
    比 TradeLog 更全。鐵則不破：助手只讀資料 + 產文字，不下單、不啟停 Bot。
    """
    client = _get_client()
    if client is None:
        raise HTTPException(status_code=400, detail=_NO_LLM_DETAIL)
    if _cloud_blocked():
        raise HTTPException(status_code=400, detail=_CLOUD_BLOCKED_DETAIL)

    db = SessionLocal()
    try:
        bot = db.query(Bot).filter(Bot.id == payload.bot_id).first()
        if not bot:
            raise HTTPException(status_code=404, detail=f"找不到 Bot #{payload.bot_id}")

        decisions = (
            db.query(DecisionLog)
            .filter(DecisionLog.bot_id == bot.id)
            .order_by(DecisionLog.created_at.desc(), DecisionLog.id.desc())
            .limit(_LESSON_DECISIONS)
            .all()
        )
        if not decisions:
            return {
                "bot_id": bot.id,
                "lessons": "（這個 Bot 還沒有決策紀錄，等它跑幾輪再來讀教訓。）",
                "stub": False,
            }

        history = _format_decision_history(decisions)
        sys_text = (
            "你是交易 Bot 的覆盤教練。看一支 Bot 的決策史，找出可學的教訓。"
            "判斷以『期望值 EV』為主、不是只看勝率（高勝率但一次大賠＝負 EV，要點出）。"
            "回答用繁體中文，簡潔具體、可執行。"
        )
        prompt = (
            f"這支 Bot：{bot.name}｜策略 {bot.strategy}｜標的 {bot.symbol}｜"
            f"參數 {json.dumps(bot.params or {}, ensure_ascii=False)}\n\n"
            f"最近 {len(decisions)} 筆決策（時間正序；含沒成交的觀望/跳過）：\n{history}\n\n"
            "請給：①一句話總評（整體像在賺還賠、什麼型態）"
            "②2~3 個具體型態觀察（如：量縮時進場常被巴、某指標值附近反覆停損）"
            "③下次可調整的 1~2 個方向（參數／風控／進出場時機）。"
        )
        try:
            lessons = _complete(client, [
                {"role": "system", "content": sys_text},
                {"role": "user", "content": prompt},
            ])
        except Exception as e:
            raise HTTPException(status_code=400, detail=_friendly_err(e))
        return {"bot_id": bot.id, "lessons": lessons, "stub": False}
    finally:
        db.close()
