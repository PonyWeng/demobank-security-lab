# 合併版安裝、服務與 Tunnel

Ubuntu VM：

```bash
git pull
bash setup.sh
bash start_service.sh
bash cloudflared.sh start
bash cloudflared.sh urls
```

setup.sh 不重設現有 .env、帳號或餘額，不自動啟動網站。需自行安裝官方 cloudflared；Tunnel start 等待五個 URL 並自動套用兩套資料庫端點及 CSRF None+Secure Cookie。超時後 Tunnel 保持運作，可用 `bash cloudflared.sh apply` 重試。Windows 直接 `python -m pip install -r requirements.txt`、`python scripts/bootstrap.py`、`python attacks/bootstrap.py`、`python run_all.py`。

|服務|Port|
|---|---|
|CSRF 銀行與 Lab 總覽 /labs|5000|
|CSRF LuckyPop|5001|
|SQL Injection|5100|
|XSS 留言板|5101|
|XSS Collector|5102|

Ubuntu 背景服務日誌：instance/services/services.log。每個 Tunnel 日誌：instance/services/tunnel-PORT.log。查看服務：`.venv/bin/python scripts/services.py status`。

停止：

```bash
bash cloudflared.sh stop
bash stop_service.sh
```

只停止本腳本建立的程序；不會掃 Port 殺程序，不會 pkill 所有 cloudflared。若 Port 被既有 run.py 佔用，start 會拒絕，請自己回到舊終端按 Ctrl+C。先前手動啟動的 Tunnel 也不會被新腳本停止。

本專案 cloudflared.sh 現在自動設定全部公開端點，Lab 總覽會立即更新。手動啟动 Tunnel 才需要自行到兩套管理中心設定；教師入口 /teacher/login，各站需分別登入。Collector 首頁開放已登入學生與教師；未登入自動前往 /login，各站仍需分別登入。

CSRF 帳號與密碼沿用先前設定，首次資料記錄在 instance/setup-credentials.json；Attacks 首次教師帳密 pony / ponypony、alice / alice001、bob / bob00100，記錄於 attacks/instance/setup-credentials.json。不共用 Session 或資料庫。Attacks 的 .env 在 attacks/.env，不能指向銀行資料庫。

模式只影響該服務的使用者 Session；教师登入與重置權限獨立驗證。SQL Injection Demo 登入繞過不能取得教師管理權。重置 CSRF 不清除 XSS，重置 Attacks 不清除銀行。

此為授權課程靶機，服務 loopback 綁定、Waitress、無 debugger。公開時保留學生存取限制，課程結束停 Tunnel；勿放真實資料。VM 上 Shell 背景服務依賴 Linux /proc，PID 與啟動時間不符時不會停止該程序。
