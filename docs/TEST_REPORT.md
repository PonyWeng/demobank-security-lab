# 實際驗收記錄

## 收合與未登入領獎流程

完整測試 19 項通過（25.79s）：下方工具預設收合、點擊展開仍可操作；未登入的活動表單 303 至銀行登入提示頁，登入後回固定活動網址，不自動扣款。Protected 仍拒絕。普通 transfer 保留 401，未接受使用者指定的任意返回 URL。

## 固定駭客帳戶與一鍵活動 Demo

更新後完整測試：**18 passed in 26.23s**。四組真實 Edge 測試均驗證原生「領取活動獎勵」表單：學生餘額扣 NT$100、DBHACKER001 餘額由 NT$5,000 增至 NT$5,100；Protected 重按後 403、學生餘額不變。自動建立帳戶不重複、不重設累積餘額；reset 後重建與 hacker-summary CLI 通過。本機教學資料庫已建立駭客帳戶，未清除既有學生資料。

2026-10-14，Windows / Python 3.13.5 / Flask 3.1.0，Playwright 控制本機 Edge（Chromium 155）。

完整測試指令：`$env:BROWSER_CHANNEL='msedge'; python -m pytest -q`。

最終結果：**16 passed in 18.40s**。

## 瀏覽器 Payload 遊樂場更新

新增 HTML Payload 產生、編輯與送出介面；run.py 一次啟動銀行及獨立 Origin 的遊樂場。更新後完整測試：**17 passed in 24.38s**。真實 Edge 操作編輯器，將金額從 100 改成 73，Vulnerable 成功扣款 73；Protected 重送完全相同 Payload 回傳 403，餘額不變。額外驗證 Windows 實際使用的 bank.localhost / evil.bank.localhost 網域組合，Cookie 與跨 Origin 轉帳行為通過。截圖：test-results/playground.png。

- 兩個獨立使用者註冊、每人 NT$5,000、不同帳號、雜湊密碼：通過。
- 登入、登出、只查自己的帳務資料：通過。
- 合法轉帳 NT$123.45，雙方餘額、共享交易紀錄正確：通過。
- Vulnerable，相同 Site 跨 Origin 攻擊者 HTML Form：真正瀏覽器成功扣款。
- Protected，相同攻擊表單：真正瀏覽器回傳 403，未扣款。
- Origin 防護（含缺少 Origin）、Session 設定隔離、Token 不能跨 Session 使用：通過。
- NaN、Infinity、零、負數、超額、精度錯誤、自轉帳、錯誤帳戶：拒絕，餘額與紀錄不變。
- 並行兩筆各 NT$3,000：只有一筆成功，餘額不會變負。
- SQLite integrity_check、foreign_key_check、總額守恆：通過。
- 重設後即使 user id 重用，舊 Session 不能登入新帳戶：通過。
- 強制在交易紀錄 INSERT 發生資料庫錯誤：503 且雙方餘額完整回滾。

| Cookie 策略 | 相同 Site / 不同 Origin | 不同 Site |
|---|---|---|
| Lax / HTTP | Cookie 附帶，302，完成轉帳 | Cookie 缺少，401，無扣款 |
| Strict / HTTP | Cookie 附帶，302，完成轉帳 | Cookie 缺少，401，無扣款 |
| None + Secure / HTTPS | Cookie 附帶，302，完成轉帳 | Cookie 附帶，302，完成轉帳 |

Cookie None 測試使用臨時 HTTPS 自簽憑證；只有測試 browser 忽略憑證錯誤。原始觀察：`test-results/browser-Lax.json`、`browser-Strict.json`、`browser-None.json`。只記錄 Cookie 是否存在，不保存 Cookie 值。HTTP .test 瀏覽器可能不送 Sec-Fetch-Site，HTTPS 輪實際觀察 same-site / cross-site。

桌面與 390px 手機截圖已目視檢查；頁面無水平溢出，交易表格在手機可水平捲動。

Docker Compose 設定解析通過；本機 Docker Desktop Linux daemon 未啟動，未實際建置或啟動容器。GCP 與 Cloudflare 部署方案已提供，未連接雲端帳號部署。
