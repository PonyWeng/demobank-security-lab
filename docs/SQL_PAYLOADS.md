# SQL Injection 課堂操作

從統一入口登入，選 SQL Lab → 開啟模擬登入。Vulnerable 模式將下面文字貼到 Username，Password 填任意文字；使用半形引號與兩個減號。

```sql
ADMIN' OR 1=1 --
ADMIN'; INSERT INTO users(username,password,isAdmin) VALUES ('hacker','9999',1); --
hacker'; DELETE FROM users WHERE username='pony'; --
'; UPDATE users SET isAdmin=1 WHERE username='pony'; --
```

每次返回資料表查看結果。第三步會刪除示範 pony，因此做第四步前由教師按「重置 SQL 示範資料」。新增 hacker 後可用 hacker／9999 正常模擬登入。

獨立資料庫為 attacks.sqlite 同目錄下的 attacks.sql-demo.sqlite（自訂 DATABASE 時沿用其檔名）。其中 users 欄位為 id、username、password、isAdmin；ADMIN／admin001 是假管理員，pony／demo001 為普通示範帳號，student／student001 為普通示範帳號。明文密碼只用於這份虛構資料。

平台真實 pony／ponypony 的登入、教師權限及銀行資料由另一份資料庫管理。SQL 注入只改示範 users；不允許 ATTACH、DDL 或讀取其他資料表。Protected 使用參數化 SQL，四種 Payload 都不會變更資料。

學生可以透過 isAdmin 與模擬登入結果觀察假管理員身分，不會得到平台管理功能。既有教師「新增使用者」仍建立真正課程帳號，與這份假 users 表不同。
