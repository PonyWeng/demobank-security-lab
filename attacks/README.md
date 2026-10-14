# SQL Injection / XSS 子模組

此目錄是合併套件的一部分，不單獨啟動。唯一完整操作說明見 [根目錄 README](../README.md)。

- SQL：5100。
- XSS：5101。
- Collector：5102。
- 首次教師帳密：pony / ponypony；學生 alice / alice001、bob / bob00100。
- 教師登入 /teacher/login，修改密碼 /password，會同步銀行與所有 Attacks 的 pony 密碼及 JSON。
- .env、SQLite 與帳密 JSON 保留在 attacks 目錄，與銀行隔離；設定檔不提交 Git。

在 repo 根目錄使用 setup.sh、start_service.sh、stop_service.sh、cloudflared.sh。Windows 使用 python run_all.py。
