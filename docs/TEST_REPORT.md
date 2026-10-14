# 實際驗收記錄

## 全頁面與統一入口檢查

新增瀏覽器逐頁稽核，31 個畫面（銀行、Playground、SQL、XSS、Collector 的登入／註冊／設定／管理／密碼與實驗頁）回應 200；CSS 載入無失敗、無 JavaScript pageerror，390px 無水平溢出。SQL／XSS 登入導覽與錯誤訊息移入卡片，學生／教師入口有清楚區別。桌面與手機截圖存於 test-results/page-audit（不提交 Git）。統一入口銀行 /labs 顯示各站登入／註冊連結，保留各實驗原風格。

## 恢復原版 SQL／XSS

從原始備份恢復深色 SQL 資料表、新增使用者，以及白色 XSS 留言板、登入／註冊版面。功能測試驗證資料表內容、教師新增使用者、學生無管理權與留言刪除。Edge 實測資料表與新增入口、全寬留言框、Protected CSP 樣式正常及 390px 手機無水平溢出。原 CSS 移至外部檔案以相容 CSP。舊資料保留，不需 setup 或資料庫重建。

## Tunnel 端點自動化

新增五條 Quick Tunnel 日誌解析與兩套 SQLite 端點同步，start 自動等待與套用，apply 可重試。2 項測試通過：完整映射、拒絕缺少／錯誤 URL 且保留設定，以及第二個資料庫失敗時回滾第一個。尚未在 Ubuntu 啟動真實 cloudflared 驗收。

## 統一教師帳密與 UI 修改

首次 pony / ponypony、alice / alice001、bob / bob00100，銀行 demo_hacker / hacker001；既有資料保留。25 項後端測試通過。新增測試分別從銀行與 SQL 教師介面修改密碼，確認兩個資料庫雜湊、兩份 JSON 同步、錯誤舊密碼與缺少 Token 拒絕，以及其他網站的舊登入失效。README 已重整為合併版唯一完整操作說明。

## 合併版服務

CSRF + SQL Injection + XSS 合併到同一 repo；24 項後端測試通過。以 run_all.py --port-offset 200 實際啟動五個服務，各自 HTTP 200。四個 Shell 腳本 Bash 語法檢查通過。SQL／XSS 另已在 Edge 實測登入繞過、Protected 拒絕、腳本執行、編碼與 CSP，以及 Collector 回應。背景服務腳本依賴 Linux /proc，尚未在 Ubuntu 實際啟停或建立公網 Tunnel；本機沒有因此對外發布新網站。機密檔案及兩套資料庫均由 gitignore 排除。

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
