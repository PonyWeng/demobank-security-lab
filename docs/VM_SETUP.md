# Ubuntu / GCP 安裝

本專案已合併 CSRF、SQL Injection 與 XSS；以根目錄 [README.md](../README.md) 作為唯一完整操作說明。

```bash
git pull
bash setup.sh
bash start_service.sh
bash cloudflared.sh start
bash cloudflared.sh urls
```

全新資料庫教師帳密固定 pony / ponypony，可在任一教師管理頁修改並同步所有 Lab。既有密碼保留。學生預設 alice / alice001、bob / bob00100；銀行模擬駭客 demo_hacker / hacker001。

端點設定、日誌與停止方式見 [SERVICES.md](SERVICES.md)。不用 Docker；初次需登入私人 GitHub repo 才能 clone。不要在仍執行舊 run.py 的狀態下啟動新背景服務。
