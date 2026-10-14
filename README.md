# Web Security Training Lab

統一課程入口 + CSRF / SQL Injection / XSS 教學靶機。Flask、SQLite、HTML/CSS/JavaScript，使用虛構帳號與帳款，不連接真實金融服務。

## 學生流程與角色

1. 開啟 5000 的課程入口。
2. 輸入課程代碼，註冊或登入一次。
3. 自動進入 /labs，選擇實驗直接進入，不需再登入或註冊。
4. SQL、XSS、Collector 用 60 秒、一次性、綁定目標 Lab 的票證建立獨立 Cookie；平台帳號與角色統一管理。

教師和學生共用登入頁。pony 的角色是教師，才會看到管理、重置、新增使用者與修改密碼。舊 /teacher/login 只保留轉址，不再有獨立教師登入。平台登出會撤銷本次課程 Session，該次登入的其他 Lab 也不能再使用。

SQL／XSS 介面採同一套設計與導覽；LuckyPop 保留不同活動網站風格。

## Port 與網址

|服務|Port|路徑|
|---|---|---|
|課程入口與 Lab 選擇|5000|/、/labs|
|CSRF DemoBank|5000|/bank|
|LuckyPop|5001|/playground|
|SQL Injection|5100|/、/simulate/login|
|XSS 留言板|5101|/|
|Collector|5102|/|

從統一入口選 Lab，不需記住各網站登入網址。服務皆綁 127.0.0.1，以 Waitress 執行，無 Flask Debugger，不使用 Docker。

## Ubuntu / GCP VM

```bash
git clone https://github.com/PonyWeng/demobank-security-lab.git
cd demobank-security-lab
bash setup.sh
bash start_service.sh
bash cloudflared.sh start
bash cloudflared.sh urls
```

私人儲存庫需先登入 GitHub。更新：先 bash stop_service.sh，再 git pull、bash setup.sh、bash start_service.sh。**升級統一入口時務必重跑 setup.sh**，它會建立票證表並一次性匯入舊 Attacks 學生到課程平台；保留既有平台密碼、角色與資料，不會替已存在的同名平台帳號改密碼。舊 Attacks 身分只作實驗快照，不再是登入權威。

setup 自動安裝依賴、建立 .venv、兩套 .env、隨機 Secret、帳號與課程代碼。已存在的設定和密碼保留。預設帳密：pony / ponypony、alice / alice001、bob / bob00100；銀行收款者 demo_hacker / hacker001，帳號 DBHACKER001。每個銀行帳戶 NT$5,000。

修改教師密碼：課程入口管理中心或各 Lab 的角色管理頁，需目前密碼、確認與 Token；兩套雜湊與 JSON 同步。紀錄在 instance/setup-credentials.json、attacks/instance/setup-credentials.json，僅供教師；不要直接改 JSON 當成修改密碼。.env、SQLite 與帳密紀錄不提交 Git。

## Windows

```powershell
python -m pip install -r requirements.txt
python scripts/bootstrap.py
python attacks/bootstrap.py
python scripts/migrate_accounts.py
python run_all.py
```

入口 http://bank.localhost:5000。終端保持開啟，Ctrl+C 停止。舊 run.py 只啟動 CSRF。

## 服務與 Tunnel

```bash
bash stop_service.sh
bash cloudflared.sh stop
.venv/bin/python scripts/services.py status
```

腳本只停止符合 PID 和程序啟動時間的本專案程序，不掃 Port 殺程序、不影響其他 cloudflared。start 若遇 Port 占用會拒絕，請自行停止舊終端的 run.py。

cloudflared.sh start 啟動五條 Quick Tunnel，最多等待 45 秒後自動套用所有公開端點與 CSRF None+Secure Cookie；不需進管理頁貼網址。若 URL 尚未齊全，Tunnel 保持運作，執行 bash cloudflared.sh apply 重試。手動設定仍可在管理頁操作。日誌在 instance/services/services.log 與 tunnel-PORT.log。

Quick Tunnel URL 改變後，學生從新的 5000 入口重新登入。GCP 不開公網上述 Port，僅透過 Tunnel 給授權學生；保留課程存取限制，課後關閉 Tunnel。Shell 背景程序管理依賴 Linux /proc。

## CSRF

從入口選銀行，設定 Vulnerable、Origin 關閉，再到 LuckyPop 按「領取活動獎勵」。活動表單提出 NT$100 轉帳到駭客帳戶，成功訊息留在活動頁，學生自行回銀行確認扣款。Protected 或 Origin 驗證會 403。下方收合唯讀說明，學生用 F12 修改 hidden recipient / amount。未登入會提示並引導入口登入；不自動轉帳。

## SQL Injection

學生已登入平台後進入 SQL，可查看 users / messages / captures 的結構與最多 100 筆資料。點「開啟模擬登入」進入 /simulate/login，Username 輸入 `' OR 1=1 -- `、密碼任意：Vulnerable 可繞過，Protected 拒絕。**模擬結果不影響平台身分或教師權限**。教師仍可新增課程使用者，正常功能永遠參數化並儲存密碼雜湊。

## XSS 與真正的實驗 Session

留言測試 `<script>alert('XSS Demo')</script>`：Vulnerable 執行，Protected 編碼成文字並加 CSP。留言板含自己的留言刪除、教師清空留言。

xss_lab_session 是伺服器簽發、实际控制留言作者及刪除身分的實驗 Session。Vulnerable 不設 HttpOnly，可被 XSS 讀取並送到 Collector。留言板的收合說明提供目前 Collector URL 的 Payload。

兩位學生各自從入口進入 XSS；攻擊者發表收集 Cookie 的留言，受害者查看後，Collector 會記錄 Cookie。攻擊者從入口選 Collector 取得 value，再用 F12 在自己的 XSS 主機替換 xss_lab_session，重整後顯示受害者的實驗身分、可用該身分發表留言。

Protected 會加 HttpOnly、輸出編碼、CSP，切換時旋轉實驗 Session 並撤銷舊 Token。實驗 Session 有 2 小時期限，重置／登出失效；它不改變課程平台角色，不能授予教師權限。平台登入 Cookie 始終 HttpOnly。只在本課程虛構帳號操作，Collector 對已登入課程學生開放。

## 測試

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest -q
```

已安裝 Edge 可設定 BROWSER_CHANNEL=msedge。測試使用臨時資料庫，涵蓋帳務、CSRF/SameSite、角色、一次性票證、SQL 模擬隔離、XSS 真實 Session 劫持、Collector、密碼同步與手機版面。統一入口及真實瀏覽器流程已驗證；Ubuntu 真實 Tunnel 部署仍以 VM 實測為準。
