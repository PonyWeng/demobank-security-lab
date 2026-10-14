# Ubuntu VM 直接執行（不使用 Docker）

```bash
sudo apt update
sudo apt install -y git gh python3 python3-venv
gh auth login
gh auth setup-git
git clone https://github.com/PonyWeng/demobank-security-lab.git
cd demobank-security-lab
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

儲存庫預設為 private，gh auth login 請登入 PonyWeng，選 GitHub.com / HTTPS / browser login；依畫面用你的瀏覽器完成授權。不要把 Token 放到 clone URL 或提交至 Git。若 VM 不方便進行授權，可改用帳號允許的 SSH deploy key。

把輸出的隨機值填到 .env 的 SECRET_KEY，設定 LAB_ACCESS_CODE。不要使用本機的舊 Secret。建立 VM 自己的管理員（互動輸入新密碼，不在指令列輸入）：

```bash
.venv/bin/python -m flask --app wsgi create-admin --username pony
.venv/bin/python run.py
```

此指令一起啟動銀行 127.0.0.1:5000 與活動站 127.0.0.1:5001。另開兩個 SSH 終端，各執行 cloudflared tunnel --url http://127.0.0.1:5000 與 cloudflared tunnel --url http://127.0.0.1:5001（cloudflared 從官方安裝）。初次從 SSH port forwarding 開啟本機銀行管理頁，貼上兩個 HTTPS 網址並保存。可在 Windows 執行 `gcloud compute ssh VM_NAME --zone ZONE -- -L 5000:127.0.0.1:5000`，再訪問 http://localhost:5000/admin/。

設定好後使用公開銀行網址登入 pony；普通學生自行註冊。跨 Site 演示可勾選 HTTPS None+Secure。課程資料庫與管理員密碼不從原 Windows 上傳；模擬駭客啟動時自動建立，教師可用 hacker-summary 查看餘額。

GCP 不開放公網 5000/5001；限制 SSH 存取來源，公開課程使用門禁與可用的 Tunnel 學生存取控制。服務不啟用 Flask debugger。詳細功能看 README.md。
