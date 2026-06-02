"""
API 路由模組
============
把原本全擠在 main.py 的 API 依功能拆成幾個檔案（router），
這樣每個檔案專注一件事，讀起來、維護起來都比較輕鬆。

- bots.py     Bot 管理（建立/編輯/刪除/啟停/執行/績效）
- backtest.py 回測
- orders.py   交易（訂單）紀錄

main.py 只負責把這些 router「掛」上去（include_router）。
"""
