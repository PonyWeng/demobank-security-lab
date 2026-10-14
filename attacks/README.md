# Attacks Lab：SQL Injection / XSS

此目錄已整合到 DemoBank repo。請在 repo 根目錄執行 `bash setup.sh` 和 `bash start_service.sh`，Windows 使用 `python run_all.py`；此子目錄不再有獨立 run.py。共用部署操作請見 ../docs/SERVICES.md。下方單獨專案的啟動描述請以這段為準。

依 DemoBank CSRF 規格重整的獨立教學專案，不與銀行共用帳號、Cookie 或資料庫。只保留 SQL Injection 與 XSS（含 Collector），無 SSTI／Command Injection。模式預設 Vulnerable，每個 Session 獨立切換。

|服務|Port|本機網址|
|---|---|---|
|SQL Injection|5100|http://sql.localhost:5100|
|XSS|5101|http://xss.localhost:5101|
|XSS Collector|5102|http://collector.localhost:5102|

5000/5001 保留給 DemoBank CSRF。本機使用不同 hostname 避免 Cookie 相互干擾。

Windows：`python -m pip install -r requirements.txt` → `python bootstrap.py` → `python run.py`。

Ubuntu：`bash setup.sh` → `.venv/bin/python run.py`。不用 Docker。服務只綁 loopback，使用 Waitress，無 Flask Debugger。

首次帳密：pony / ponypony（教師）、alice / alice001、bob / bob00100。純課堂假帳號；重跑 setup 不重設既有密碼。Secret 隨機產生，.env／instance 均不提交 Git。

教師入口 `/teacher/login` 永遠參數化，正常登入後進入 `/admin`：查看註冊名單、儲存三個 HTTPS Tunnel origin、輸入 RESET 重置學生與留言／收集紀錄。普通 SQL 注入登入不會得到教師管理權。初次設定公開主機用 SSH port forwarding 到本機；設定儲存後立即生效，重新整理各站即可。

Cloudflare：另開終端 `cloudflared tunnel --url http://127.0.0.1:5100`，5101、5102 同樣。或 `bash start_up_to_cloudflare.sh` 一次啟動，Ctrl+C 只停止這三條 Tunnel，不影響 CSRF。只填 origin、不含路徑。僅限授權學生；可設定 LAB_ACCESS_CODE，Cookie 策略以 .env 管理。請勿串接真實帳號、資料或服務。

SQL Demo：登出後 username 輸入 `' OR 1=1 -- `、密碼任意；Vulnerable 通過，Protected 拒絕。此安全模式針對 SQL 注入，不代表整個教學站可作正式產品。

XSS Demo：登入後發表 `<script>alert('XSS Demo')</script>`；Vulnerable 執行、Protected 以文字顯示並用 CSP 拒絕 inline script。收集測試只使用 fake_session 假標記；真正 Session 仍 HttpOnly，不提供 Session 偽造後門。Collector 查看頁需教師登入。

SQLite 儲存密碼雜湊、留言、公開端點；重置後其他登入失效。正常資料操作全部參數化，只有 SQL Vulnerable 的登入查詢刻意拼接。測試：`python -m pytest -q`（另外安裝 pytest）。
