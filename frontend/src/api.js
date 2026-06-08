// ============================================================
// API 呼叫層
// ============================================================
// 把「跟後端溝通」的程式都集中在這裡，元件只要呼叫 api.xxx() 即可，
// 不用在每個頁面重複寫 fetch 的細節。

// 後端伺服器網址。
// 優先讀環境變數 VITE_API_URL（搬電腦／部署時不用改程式碼），
// 沒設定時退回本機預設值，所以新手「什麼都不設定」也能直接跑。
//
// 觀念：Vite 只會把「VITE_ 開頭」的環境變數送進前端程式碼，
// 透過 import.meta.env.VITE_xxx 取用。要覆寫就在 frontend/ 建 .env.local
// 寫一行 VITE_API_URL=...（.env.local 已被 .gitignore 忽略，不會上傳）。
const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// 共用的請求函式：負責組網址、帶 JSON header、處理錯誤
async function request(path, options = {}) {
  const res = await fetch(BASE_URL + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  // 後端回傳非 2xx 時，丟出錯誤讓畫面顯示
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API 錯誤 ${res.status}：${text}`);
  }
  return res.json();
}

// 把各個 API 包成好懂的函式
export const api = {
  // 取得交易環境狀態（模擬／實盤）
  getStatus: () => request("/status"),

  // 取得帳戶資訊
  getAccount: () => request("/account"),

  // 取得所有 Bot
  getBots: () => request("/bots"),

  // 建立一個 Bot
  createBot: (data) =>
    request("/bots", { method: "POST", body: JSON.stringify(data) }),

  // 讓某個 Bot 立刻跑一次策略
  runBot: (id) => request(`/bots/${id}/run`, { method: "POST" }),

  // 取得交易紀錄
  getTrades: () => request("/trades"),

  // 編輯 Bot
  updateBot: (id, data) =>
    request(`/bots/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  // 只更新風控水位線（圖表拖曳止損/止盈線即時連動）。只送有改的欄位。
  updateBotRisk: (id, risk) =>
    request(`/bots/${id}/risk`, { method: "PUT", body: JSON.stringify(risk) }),

  // 刪除 Bot
  deleteBot: (id) => request(`/bots/${id}`, { method: "DELETE" }),

  // 啟動 Bot 定時執行
  startBot: (id) => request(`/bots/${id}/start`, { method: "POST" }),

  // 停止 Bot 定時執行
  stopBot: (id) => request(`/bots/${id}/stop`, { method: "POST" }),

  // 執行回測
  runBacktest: (data) =>
    request("/backtest", { method: "POST", body: JSON.stringify(data) }),

  // 全自動掃描（最強）：程式自己跑遍所有策略×參數，依 EV 排名挑最佳並存歷史
  autoBacktest: (data) =>
    request("/auto-backtest", { method: "POST", body: JSON.stringify(data) }),

  // 一次性查某股票最新價（即時報價的 WebSocket 在 hooks/useLiveQuote.js 另外處理）
  getQuote: (symbol) => request(`/quotes/${symbol}`),

  // 取歷史日 K 線（給原生圖表 lightweight-charts 畫蠟燭用）
  getBars: (symbol, days = 120, source = "alpaca") =>
    request(`/bars/${symbol}?days=${days}&source=${source}`),

  // ===== AI 策略探勘（漏斗式海選）=====
  // 回傳值得部署的策略推薦清單（量能→情緒→EV 海選）。refresh=true 強制重算。
  getRecommendations: ({ days = 365, source = "alpaca", refresh = false } = {}) =>
    request(`/ai-recommendations?days=${days}&source=${source}&refresh=${refresh}`),

  // ===== 基本面 / 財報 / 新聞 =====
  getProfile: (symbol) => request(`/fundamentals/${symbol}`),
  getFinancials: (symbol, period = "annual") =>
    request(`/fundamentals/${symbol}/financials?period=${period}`),
  getNews: (symbol) => request(`/fundamentals/${symbol}/news`),
  getActions: (symbol) => request(`/fundamentals/${symbol}/actions`),

  // ===== Phase 5：策略工作台 =====
  // 策略方案 CRUD
  getPresets: () => request("/presets"),
  createPreset: (data) =>
    request("/presets", { method: "POST", body: JSON.stringify(data) }),
  updatePreset: (id, data) =>
    request(`/presets/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deletePreset: (id) => request(`/presets/${id}`, { method: "DELETE" }),

  // 對某方案一鍵跑回測（Python），回結果並存一筆回測紀錄
  backtestPreset: (id, options = {}) =>
    request(`/presets/${id}/backtest`, {
      method: "POST",
      body: JSON.stringify(options),
    }),

  // 回測歷史（依 EV 排序）；favorite=true 只看好策略
  getBacktestRuns: (favorite = false) =>
    request(`/backtest-runs${favorite ? "?favorite=true" : ""}`),
  getBacktestRun: (id) => request(`/backtest-runs/${id}`),
  // 某筆回測的 quantstats HTML 績效報表「完整網址」（給 <a target="_blank"> 開新分頁用，
  // 回的是 HTML 不是 JSON，所以給網址、不走 request()）
  reportUrl: (id) => `${BASE_URL}/backtest-runs/${id}/report`,
  // 收藏/取消收藏某筆回測
  favoriteBacktestRun: (id, isGood = true) =>
    request(`/backtest-runs/${id}/favorite?is_good=${isGood}`, { method: "PUT" }),

  // ===== Claude 思考助手（步驟 4 為 stub）=====
  // 聊天（無狀態，送完整 messages）
  sendChat: (messages) =>
    request("/chat", { method: "POST", body: JSON.stringify({ messages }) }),
  // 對某筆回測做事後檢討
  postmortem: (runId) =>
    request("/chat/postmortem", {
      method: "POST",
      body: JSON.stringify({ run_id: runId }),
    }),

  // ===== Phase 9：探討/檢討檔案記憶（唯讀）=====
  // 路標清單（每筆 run_id / file / strategy / symbol / summary）
  getExplorations: () => request("/explorations"),
  // 某篇探討的完整 markdown 內容（{ name, content }）
  getExploration: (name) => request(`/explorations/${encodeURIComponent(name)}`),
};
