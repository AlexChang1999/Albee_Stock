// ============================================================
// API 呼叫層
// ============================================================
// 把「跟後端溝通」的程式都集中在這裡，元件只要呼叫 api.xxx() 即可，
// 不用在每個頁面重複寫 fetch 的細節。

// 後端伺服器網址（開發時固定在本機 8000 埠）
const BASE_URL = "http://127.0.0.1:8000";

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

  // 刪除 Bot
  deleteBot: (id) => request(`/bots/${id}`, { method: "DELETE" }),

  // 啟動 Bot 定時執行
  startBot: (id) => request(`/bots/${id}/start`, { method: "POST" }),

  // 停止 Bot 定時執行
  stopBot: (id) => request(`/bots/${id}/stop`, { method: "POST" }),

  // 執行回測
  runBacktest: (data) =>
    request("/backtest", { method: "POST", body: JSON.stringify(data) }),
};
