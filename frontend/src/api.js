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

  // ===== redesign Phase 4：模式 B 全局自動化規則（規則存 DB，可編輯）=====
  // 看目前規則與名額
  getAutomation: () => request("/automation"),
  // 編輯規則（只送有帶的欄位；改 scan_hour 後端會即時重掛排程）
  updateAutomation: (body) =>
    request("/automation", { method: "PUT", body: JSON.stringify(body) }),
  // 手動觸發一輪自動部署。dry_run=true 只預覽會部署誰、不真的建；force=true 略過總開關
  runAutomation: ({ force = false, dry_run = false } = {}) =>
    request(`/automation/run?force=${force}&dry_run=${dry_run}`, {
      method: "POST",
    }),

  // ===== Phase 5：策略工作台 =====
  // 策略方案 CRUD
  getPresets: () => request("/presets"),
  createPreset: (data) =>
    request("/presets", { method: "POST", body: JSON.stringify(data) }),
  updatePreset: (id, data) =>
    request(`/presets/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deletePreset: (id) => request(`/presets/${id}`, { method: "DELETE" }),

  // 好策略「一鍵轉 Bot」：把方案複製成新 Bot 實跑（options 可帶 name / trade_amount）
  presetToBot: (id, options = {}) =>
    request(`/presets/${id}/to-bot`, {
      method: "POST",
      body: JSON.stringify(options),
    }),

  // 主動提醒：負 EV 未檢討、好策略未實跑等待辦事項（給橫幅顯示）
  getReminders: () => request("/reminders"),

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

  // ===== Phase 9：決策審計（Phase 6 step-08 的軌跡）=====
  // 某 Bot 最近的決策紀錄（含沒成交的觀望/跳過），依時間倒序
  getBotDecisions: (botId, limit = 50) =>
    request(`/bots/${botId}/decisions?limit=${limit}`),

  // ===== Phase 9：探討/檢討檔案記憶（唯讀）=====
  // 路標清單（每筆 run_id / file / strategy / symbol / summary）
  getExplorations: () => request("/explorations"),
  // 某篇探討的完整 markdown 內容（{ name, content }）
  getExploration: (name) => request(`/explorations/${encodeURIComponent(name)}`),

  // ===== Phase 9：策略知識庫 / 組合進化（Phase 8 端點）=====
  // 知識清單（可選 status 篩選：candidate/validated/curated/rejected）
  getKnowledge: (status) =>
    request(`/knowledge${status ? `?status=${status}` : ""}`),
  // 排行：依 OOS EV 由高到低（預設 validated；可改 curated）
  getKnowledgeRanking: (status = "validated") =>
    request(`/knowledge/ranking?status=${status}`),
  getKnowledgeItem: (id) => request(`/knowledge/${id}`),
  // 跑驗證管線（OOS + walk-forward）
  validateKnowledge: (id, options = {}) =>
    request(`/knowledge/${id}/validate`, {
      method: "POST",
      body: JSON.stringify(options),
    }),
  // 人在迴路：晉升（validated→curated）/ 退回（→rejected，附理由）
  promoteKnowledge: (id) =>
    request(`/knowledge/${id}/promote`, { method: "POST" }),
  rejectKnowledge: (id, reason = "") =>
    request(`/knowledge/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  // ===== Phase 10：公司戰情（各部門現況聚合，唯讀）=====
  getCompanyOverview: () => request("/company/overview"),

  // 機會清單：常駐探勘持久化的候選，依 OOS EV 由高到低（可選 limit / status）
  getOpportunities: ({ limit = 50, status } = {}) =>
    request(`/opportunities?limit=${limit}${status ? `&status=${status}` : ""}`),

  // ===== Phase 10 step-06：董事會核准（Bot 進真錢，人在迴路）=====
  // 晉升清單：預設「待核（proposed_live）」；可帶 status 看其他狀態
  getPromotions: (status) =>
    request(`/promotions${status ? `?status=${status}` : ""}`),
  // 系統/人提議某 Bot 上真錢（附達標證據）；未達標後端回 409
  proposePromotion: (botId) =>
    request(`/promotions/${botId}/propose`, { method: "POST" }),
  // 老闆核准（→ approved_live，只是人工旗標，不放行真錢）
  approvePromotion: (botId) =>
    request(`/promotions/${botId}/approve`, { method: "POST" }),
  // 老闆退回（→ rejected，附理由）
  rejectPromotion: (botId, reason = "") =>
    request(`/promotions/${botId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  // ===== Phase 10 step-03：因子數值表（蒐集員主管報表，唯讀）=====
  // 因子快照清單：依觀測時點由新到舊（可選 symbol / limit）
  getFactors: ({ symbol, limit = 100 } = {}) =>
    request(`/factors?limit=${limit}${symbol ? `&symbol=${symbol}` : ""}`),
  // CSV 匯出「完整網址」（回 CSV 不是 JSON，給 <a href> 下載用，不走 request()）
  factorsCsvUrl: (symbol) =>
    `${BASE_URL}/factors/export.csv${symbol ? `?symbol=${symbol}` : ""}`,

  // ===== Phase 10 step-04：市場蒐集員（爬蟲收料，靈感收件匣）=====
  // 收件匣素材清單：依抓取時間由新到舊（可選 limit / status）
  getCollectorFinds: ({ limit = 50, status } = {}) =>
    request(`/collector/finds?limit=${limit}${status ? `&status=${status}` : ""}`),
  // 人工策展：標記一筆素材的狀態（new/triaged/built/discarded）
  updateCollectorFind: (id, status) =>
    request(`/collector/finds/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
};
