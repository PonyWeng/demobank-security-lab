# DemoBank Web Security Training Lab

Ubuntu VM 一鍵設定：clone 後執行 `bash setup.sh`，再用 `cat instance/setup-credentials.json` 查看首次建立的帳號密碼及課程代碼；執行 `.venv/bin/python run.py` 啟動。腳本自動建立 .env 與 pony 管理員、alice、bob、demo_hacker，重跑保留現有資料。詳見 [VM_SETUP.md](docs/VM_SETUP.md)。

目前 Playground 已移除所有 Payload 輸入、編輯與複製介面。下方僅有預設收合的唯讀教學說明；學生以 F12 → Elements → reward-form 修改 recipient／amount 的 hidden input value，再按領取按鈕。重新整理恢復固定駭客帳號與 NT$100。下文較早的編輯器操作以此最新流程為準。

Python Flask / SQLite / HTML / CSS / JavaScript 的完整本機教學銀行。所有金額為虛構，不連接金融服務。轉帳使用整數分與原子交易；密碼以 Werkzeug scrypt 雜湊；銀行 SQL 全部參數化。只有 `/transfer` 的 CSRF 驗證可刻意關閉。帳戶 API 只查詢登入者，無任意使用者 id 讀取介面。

## Windows 啟動（PowerShell）

在本專案目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
```

將產生的值填入 `.env` 的 `SECRET_KEY`。只用一個終端機執行（銀行與 Payload 遊樂場會一起啟動）：

```powershell
.\.venv\Scripts\python run.py
```

打開銀行的「安全實驗室」，按「開啟 Payload 遊樂場」。輸入收款帳號與金額，按「產生 Payload」，可修改 HTML 後按「送出 Payload」。不需要另外啟動 attacker.py；若之前已啟動，請先 Ctrl+C 停止，避免 5001 連接埠衝突。

遊樂場網址：<http://evil.bank.localhost:5001/playground>。可測試無 Token、錯誤 Token、Protected、Vulnerable 與 Origin 驗證。送出後目前分頁會顯示銀行回應，按上一頁回到遊樂場。HTML 編輯器只擷取 POST 表單欄位，目標限定本課程銀行；不執行貼入的腳本。

銀行：<http://bank.localhost:5000>。攻擊者：<http://evil.bank.localhost:5001>（相同 Site、不同 Origin）。Chrome/Edge 通常將 `*.localhost` 解析到 loopback；若環境不支援，使用 hosts 檔設定測試名稱，或依下方自動化測試方式啟動。

**不要直接用 localhost:5001 當隔離攻擊者主機**：Cookie 不依 port 隔離；本方案使用不同 hostname，銀行 Cookie 為 host-only 且 HttpOnly，因此攻擊者伺服器不會收到銀行 Cookie。攻擊頁只有 HTML Form，沒有讀 Cookie 的程式。

## Ubuntu / GCP VM

```bash
sudo apt update
sudo apt install -y python3 python3-venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))'
# 編輯 .env 的 SECRET_KEY
.venv/bin/python run.py
```

使用 Waitress WSGI server；無 debugger、無 debug reloader。預設只綁 127.0.0.1。GCP 防火牆不要開放 5000/5001；SSH 僅限教師 IP 或 IAP。長期執行可用 systemd，以低權限專用使用者啟動上述命令，設定 WorkingDirectory 與 EnvironmentFile 絕對路徑；只有 instance 目錄需要寫入權限。

## Docker Compose

建立 `.env` 並設定 Secret 後：

```bash
docker compose up --build -d
docker compose logs
docker compose exec bank flask --app wsgi seed-lab
docker compose exec bank flask --app wsgi reset-lab --yes
docker compose down
```

資料儲存在 bank-data volume，down 不刪除資料。容器以非 root 執行、drop capabilities，port 僅發布至主機 loopback。`DATABASE` 使用預設 `instance/demobank.sqlite`，不要設定 Windows 絕對路徑給容器。需要完整重建資料時執行 reset-lab；刪除 volume 前先確認資料不需保留。

## 教學流程

### 一鍵 Demo：固定模擬駭客

活動按鈕新增模擬提示：未登入先彈出「尚未登入，無法領獎，系統將自動跳轉」，按確定後前往銀行登入；登入後回活動頁需再按一次。轉帳成功後返回 LuckyPop，顯示「領取成功！請至帳戶確認已領取的獎勵金。」並留在活動網站，學生自行回銀行查看實際扣款。這段成功文案是虛構誘餌，不代表銀行入帳；Protected 拒絕時保留 403，絕不顯示成功。活動缺少登入的初始回應為 401 提示頁，由頁面腳本引導登入；一般 transfer 不變。

LuckyPop 下方教學與 Payload 工具預設收合，點「展開教學說明與 Payload 編輯器」才顯示。未登入點上方領獎按鈕，透過 `/transfer?reward=1` 導向銀行登入頁顯示提示；登入成功回到固定的 PLAYGROUND_URL，使用者需再按一次，不自動轉帳。一般 `/transfer` 缺少登入 Cookie 仍回 401；已登入的 Protected 領獎仍回 403。登入頁不接受任意 next 網址。課程門禁啟用時也保留此返回流程。

啟動銀行時自動建立 `demo_hacker` / `DBHACKER001`，初始 NT$5,000。重啟不會清空餘額或重複建立；reset-lab 清除學生資料後，重建此帳戶。該帳戶使用不公開的隨機密碼，學生不能註冊保留名稱；教師不用登入它，直接查看摘要：

```cmd
python -m flask --app wsgi hacker-summary
```

Demo：學生登入自己的銀行 → 安全實驗室切 Vulnerable、關閉 Origin 驗證 → 開啟 LuckyPop → 按上方「領取活動獎勵」。原生跨來源 HTML Form 固定轉 NT$100 給 `DBHACKER001`，不含 Token、不讀取 Cookie。回銀行查看餘額扣 100 與交易明細，再用 CLI 確認駭客收款。Protected 重按相同活動按鈕回傳 403，餘額不變。未登入則 401，餘額不足則 400。初始 Protected 預設保留，需教師／學生自行切換 Vulnerable。

下方 Payload 編輯器也預填駭客帳號與 NT$100，可複製，或改成兩人互相實驗的帳戶。上方活動按鈕不受下方編輯器修改影響。

1. 註冊 alice 與 bob（密碼至少 8 字元）。每人初始 NT$5,000。用不同瀏覽器 Profile 保持兩人登入。
2. 複製 bob 帳號，在 alice 帳務頁正常轉帳；双方可看同一筆交易。
3. alice → 安全實驗室 → Vulnerable、取消 Origin 驗證。保持登入。
4. 開啟獨立攻擊者網站，填 bob 帳號、100，按「發送偽造轉帳」。相同 Site 的跨 Origin 表單會夾帶 Cookie，完成轉帳。
5. alice 切回 Protected，再提交完全相同的攻擊表單：403。合法銀行表單含正確 Token，仍可正常轉帳。
6. 切回 Vulnerable 並啟用 Origin 驗證：攻擊表單被 403 拒絕；銀行正常表單通過。

打開 DevTools Network、Preserve log，在 POST /transfer 查看 Request Headers 的 Cookie、Origin、Sec-Fetch-Site；Response 的狀態碼與 Location。HttpOnly Cookie 可在 DevTools 檢查，攻擊者 JavaScript 不能取得。表單提交不需要 CORS 授權；瀏覽器不能讓攻擊者程式任意讀取回應。

## SameSite 比較

Cookie 策略由 `.env` 的 `COOKIE_SAMESITE` 和 `COOKIE_SECURE` 控制，教師重啟服務並重新登入。不要在同一 browser profile 混用前一輪 Cookie。

| 表單來源 | Lax | Strict | None + Secure |
|---|---|---|---|
| 不同 Origin、相同 Site，POST | 附帶 | 附帶 | 附帶 |
| 不同 Site，POST | 不附帶 | 不附帶 | HTTPS 可附帶 |

不同 port 不等於不同 Site。Site 由 scheme 與可註冊網域決定；Origin 還包含 host 與 port。此表只針對頂層 HTML Form POST；不是 iframe、fetch、頂層 GET 的通則。瀏覽器隱私政策可能進一步限制 Cookie。None 必須設定 Secure，真正跨 Site 實驗使用 HTTPS。轉帳缺少 Cookie 時回傳 401，避免重新發出登入 Cookie 覆寫原本 Session；Token 或 Origin 驗證失敗才是 403。

自動化測試使用 host resolver：bank.lab.test、evil.lab.test（相同 Site）、attacker.other.test（不同 Site）；HTTPS 輪使用臨時自簽憑證與測試瀏覽器 ignore_https_errors。正式對學生使用有效 TLS 憑證。

## 存取控制與 Cloudflare Tunnel

1. 專用 GCP VM / 專用課程資料庫，不與正式服務、IAM 金鑰或真實資料共置。
2. 在 Cloudflare Zero Trust 建立 Tunnel；銀行 hostname 路由至 `http://127.0.0.1:5000`，攻擊者 hostname 至 `http://127.0.0.1:5001`。
3. **兩個 hostname 都先建立 Access self-hosted application**，Allow 僅授權學生 email/group，啟用身分提供者 MFA；不要建立 Everyone/BYPASS 規則。學生先分別訪問兩站完成 Access 登入，再開始實驗，避免 Access 登入頁干擾結果。
4. 額外設定強 `LAB_ACCESS_CODE` 並透過課程管道提供；此為第二道共享門禁，不取代 Access 個人身分驗證。不要把課程代碼當銀行密碼。
5. `.env` 設定 `BANK_ORIGIN=https://bank.your-domain.example`、`BANK_HOSTS=bank.your-domain.example`、`ATTACK_TARGET=https://bank.your-domain.example`、`COOKIE_SECURE=true`。相同 Site 測試用同一註冊網域不同子網域；不同 Site 測試需另一個註冊網域。
6. 如需跨 Site CSRF 成功演示，設定 `COOKIE_SAMESITE=None`；演示完改回 Lax 與 Protected。Tunnel 本身不等於 Access 授權；不要使用公開 Quick Tunnel 開放靶機。
7. Tunnel 僅 outbound；VM 無公網 bank port、無直接 origin bypass。禁止共享 localhost 環境與不可信程序。課程後撤銷 Access 與 reset-lab；每班可用獨立 VM 或 Compose 專案隔離資料。

銀行不信任任意 X-Forwarded-* header；Origin 與設定的外部 BANK_ORIGIN 精確比較。Tunnel 應保留原始 Host。無 CORS permissive header。日誌不記錄密碼/Token/Cookie；瀏覽器測試 JSON 只記錄 Cookie 是否存在。

## 重設與實驗帳號

### pony 管理中心

管理中心可直接儲存「銀行網址」與「Playground 網址」（只填 origin，例如 https://random.trycloudflare.com）。設定保存於 SQLite，立即生效且重啟保留，優先於 .env；兩個服務使用 run.py 啟動時會同步讀取。設定不會清除帳號或重置實驗模式。

Windows 開三個 CMD：第一個 `python run.py`，第二個 `cloudflared tunnel --url http://127.0.0.1:5000`，第三個 `cloudflared tunnel --url http://127.0.0.1:5001`。pony 從本機銀行登入管理中心，貼上兩個產生的 HTTPS 網址。需要跨 Site 成功 Demo 時勾選「HTTPS 跨 Site Demo」，公開銀行 Cookie 使用 None + Secure；本機 HTTP 保留原 Cookie 策略。之後学生先在新的公開銀行網址登入，再訪問公開 Playground /playground。Tunnel 重新啟動產生新網址後，再次更新欄位即可，頁面需重新整理。

普通 Quick Tunnel URL 不是個人授權機制；限授權課程時段使用並設定 LAB_ACCESS_CODE，課程結束關閉 Tunnel。支援版本可依 Cloudflare 的 Protected Quick Tunnel 文件限制學生 email；兩站須先完成身分驗證。Cloudflare 驗證 Cookie 政策可能影響跨 Site POST，請先實測。不要把管理員密碼分享給學生。

現有 pony 已在本機資料庫升為管理員；登入後導覽列顯示「管理中心」，網址 `/admin/`。可看註冊學生人數、所有帳號／銀行帳號／餘額及駭客餘額。按重新整理取得最新數據。管理權限由資料庫 is_admin 驗證，註冊 pony 名稱或提交角色欄位不會自動取得管理權限。

網頁重置須管理員身分、正確 CSRF Token，以及確認欄位輸入 RESET。刪除學生帳號與所有交易，保留管理員、駭客帳號與密碼，所有保留帳戶恢復 NT$5,000；其他 Session 失效，發起操作的管理員保持登入。CLI reset-lab 同樣保留管理員與駭客，但所有 Session 失效。不要在尚未完成的課程中重置。

```powershell
python -m flask --app wsgi reset-lab --yes
python -m flask --app wsgi seed-lab
```

seed-lab 互動輸入新密碼，建立 alice / DB100001、bob / DB100002（已存在者保留）。完整重設請先 reset，再 seed。reset 原子清空帳號、餘額、紀錄並旋轉資料世代，因此即使 SQLite 重用 user id，舊 Session 也失效。此功能僅 CLI，無網頁管理刪除端點。

## 執行測試

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest -q
```

已安裝 Edge 可省略 Chromium 下載：PowerShell `$env:BROWSER_CHANNEL='msedge'`，Linux `BROWSER_CHANNEL=msedge python -m pytest -q`（須已安裝 Edge）。Ubuntu Chromium 安裝可使用 `python -m playwright install --with-deps chromium`。

測試使用獨立臨時 SQLite，包含註冊/登入/登出、帳務所有權、合法與偽造轉帳、Origin、整數分金額、錯誤回滾、並行餘額、外鍵、總額守恆、重設失效與真實瀏覽器 SameSite 矩陣。產生 `test-results/browser-*.json` 與桌面/手機截圖。測試不修改教學資料庫。

後續模組請參考 [docs/EXTENDING.md](docs/EXTENDING.md)。本次不實作 XSS/CORS/SQLi/IDOR 攻擊端點。

參考： [MDN SameSite Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie)、[MDN Site](https://developer.mozilla.org/en-US/docs/Glossary/Site)、[Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/get-started/)。
