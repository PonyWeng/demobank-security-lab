# Web Security Training Lab

Flask、SQLite、HTML/CSS/JavaScript 的大學資安教學靶機，包含 CSRF、SQL Injection、XSS。只使用虛構帳號與帳款，不串接金融服務。銀行與 Attacks 資料庫、Cookie 分離；模式以各網站的使用者 Session 切換。

## 服務與 Port

|服務|Port|本機網址|
|---|---|---|
|DemoBank／Lab 總覽|5000|http://bank.localhost:5000/labs|
|LuckyPop CSRF 活動站|5001|http://evil.bank.localhost:5001/playground|
|SQL Injection|5100|http://sql.localhost:5100|
|XSS 留言板|5101|http://xss.localhost:5101|
|XSS Collector|5102|http://collector.localhost:5102|

服務使用 Waitress，只監聽 127.0.0.1，不開 Flask Debugger。不需要 Docker。

## Ubuntu / GCP VM

私人儲存庫首次 clone，請先以 GitHub CLI 或 SSH key 登入 PonyWeng：

```bash
git clone https://github.com/PonyWeng/demobank-security-lab.git
cd demobank-security-lab
bash setup.sh
bash start_service.sh
```

已有專案：先停服務，再 `git pull`、`bash setup.sh`、`bash start_service.sh`。setup 自動安裝 Python 依賴、建立 .venv、兩套 .env、隨機 Secret 與初始帳號；重跑不覆寫既有密碼、餘額或設定。Linux 背景服務日誌在 instance/services/services.log。

```bash
bash stop_service.sh
.venv/bin/python scripts/services.py status
```

腳本只停止符合 PID 與啟動時間紀錄的程序。遇到 Port 已被舊服務占用，請回到舊終端 Ctrl+C，不會自動殺其他程序。

## Windows

```powershell
python -m pip install -r requirements.txt
python scripts/bootstrap.py
python attacks/bootstrap.py
python run_all.py
```

保持終端開啟，Ctrl+C 停止。舊的 `python run.py` 只啟動 CSRF 兩站；完整套件請使用 run_all.py。

## 初始教學帳密與修改密碼

|帳號|首次密碼|用途|
|---|---|---|
|pony|ponypony|各 Lab 教師管理員|
|alice|alice001|學生 Demo|
|bob|bob00100|學生 Demo|
|demo_hacker|hacker001|僅 DemoBank，收款帳戶 DBHACKER001|

以上是全新資料庫的預設；已有資料庫保留你先前設定的密碼。每個銀行帳號初始 NT$5,000。不同網站仍需分別登入，帳密相同不代表共用登入 Cookie。

銀行登入 pony 後到「管理中心 → 修改教師密碼」，或 Attacks 使用 `/teacher/login` 登入後到「修改教師密碼」。輸入目前密碼、新密碼與確認，可同步更新銀行、SQL、XSS、Collector 的 pony 密碼；其他登入失效，目前教師保持登入。此功能始終驗證角色、目前密碼與 CSRF Token。其他學生帳密不會被修改。

本機帳密紀錄：instance/setup-credentials.json 與 attacks/instance/setup-credentials.json。介面修改 pony 密碼時同步更新兩份 JSON；直接編輯 JSON 不會更新登入密碼。.env、JSON、SQLite 均不提交 Git。完整同步需先執行 setup，確保两套資料庫與管理員存在。

## Cloudflare Tunnel 與端點

先安裝官方 cloudflared，再執行：

```bash
bash cloudflared.sh start
bash cloudflared.sh urls
# 課程結束
bash cloudflared.sh stop
```

此腳本啟動五條 Quick Tunnel，等待最多 45 秒取得網址後，自動寫入銀行與 Attacks 的五個端點，並啟用 CSRF HTTPS 跨 Site Cookie。成功會顯示「All five public endpoints applied automatically」，不需手動貼設定或重啟網站。網址若尚未產生，Tunnel 保持運作，可執行 `bash cloudflared.sh apply` 重試；五個網址未齊全或格式錯誤時不覆寫原設定。urls 只顯示網址。停止只處理本腳本的 Tunnel，保留其他專案連線。各日誌在 instance/services/tunnel-PORT.log。

如果不用本專案的 Tunnel 腳本、而是手動執行 cloudflared，才需要以 SSH port forwarding 訪問管理頁：銀行設定 5000/5001；SQL `/teacher/login` → 管理中心設定 5100/5101/5102。只填 `https://主機`，不含路徑。端點儲存 SQLite 後立即生效，優先於 .env。新網址自動套用後，學生仍需在新的公開銀行登入。

CSRF 公開跨 Site Demo 勾選銀行管理頁的「HTTPS 跨 Site Demo：None + Secure」，並在公開銀行重新登入。切勿只登入 localhost 再操作公網活動站。普通 Quick Tunnel 不等於學生授權機制；設定課程門禁及可用的學生存取限制。GCP 不開公網 5000/5001/5100/5101/5102；課程結束停 Tunnel。

## 教學操作

**CSRF**：學生登入銀行，選 Vulnerable、Origin 關閉；LuckyPop 按「領取活動獎勵」，會提出 NT$100 轉帳至 DBHACKER001。成功訊息停留活動頁，學生回銀行確認實際扣款。Protected 或 Origin 驗證開啟會 403。下方唯讀說明預設收合；學生用 F12 → Elements → reward-form 修改 hidden recipient／amount。未登入會提示並引導登入，登入後需再按一次。

**SQL Injection**：普通 `/login` 的 username 輸入 `' OR 1=1 -- `、密碼任意，Vulnerable 可繞過，Protected 使用參數化與密碼雜湊驗證而拒絕。此注入登入不會獲得教師管理權；`/teacher/login` 永遠安全驗證。登入前也可到 `/security` 切換模式。

SQL 登入後保留原本深色「Database Structure & Data」頁，可查看教學 users、messages、captures 的欄位及最多 100 筆資料。以正確 pony 帳密登入，可按 Add new User 建立使用者與指定角色，密碼儲存雜湊；設定資料表不公開。XSS 恢復原版白色留言板與全寬留言框、原版登入／註冊畫面，保留自己的留言刪除与教師清空留言功能。

**XSS**：登入留言板發表 `<script>alert('XSS Demo')</script>`；Vulnerable 不安全輸出會執行，Protected 以文字顯示並加入 CSP。Collector 僅用於本課程 fake_session 假標記，查看紀錄需在 Collector 登入（學生也可）；真正登入 Cookie 一直維持 HttpOnly。

各設定頁顯示改了什麼、加在哪個檔案與函式。銀行管理中心可查看所有餘額及學生；Attacks 管理中心可查看帳號與端點。重置要輸入 RESET 並驗證 Token；銀行重置不影響 XSS，Attacks 重置不影響銀行。CSRF 重置保留教師與駭客帳密，餘額恢復 NT$5,000。

## 測試與資料

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest -q
```

已有 Edge 時可設定 BROWSER_CHANNEL=msedge。測試使用獨立臨時資料庫；涵蓋帳務一致性、CSRF／SameSite、管理權限、SQL／XSS 模式與教師密碼同步。Linux 背景腳本尚需在 Ubuntu 實際驗收；本機已檢查 Bash 語法及五服務 HTTP 回應。

更多部署細節：[docs/SERVICES.md](docs/SERVICES.md)。驗收紀錄：[docs/TEST_REPORT.md](docs/TEST_REPORT.md)。
