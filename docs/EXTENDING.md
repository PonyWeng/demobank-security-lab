# 獨立漏洞模組

目前僅 CSRF 完整實作。`bank/security.py:settings()` 是模式 registry；未實作項目固定 False，不能假裝已支援。

每個新 lab 建立自己的 Flask Blueprint、URL `/labs/<name>/...`、模板與測試。設定存於 Session 的独立 key，設定 POST 永遠驗證 CSRF Token。正常 `/register`、`/login`、`/transfer` 與帳務 API 維持參數化 SQL、Jinja autoescape 與物件所有權驗證。

- XSS：只在獨立示範頁刻意使用不安全輸出；安全分支用 autoescape。CSP 只針對該 lab endpoint 調整，勿全域取消。
- CORS：獨立資料端點，比較精確來源白名單與錯誤反射 Origin；不得更改帳務 API。
- SQLi：使用另一個純假資料資料庫，僅示範端點允許字串拼接。銀行資料庫永遠使用參數化查詢。
- IDOR：另一套假物件；受保護分支同時查物件 id 與 session user_id。銀行帳號不可透過請求指定轉出者。

每個 lab 分別測試開關、保護分支、跨使用者操作與其他 lab 不受影響。不要加入任意 SQL 執行、Shell 或真實外部服務。
