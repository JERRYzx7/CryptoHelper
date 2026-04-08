# 🚀 Fly.io 部署指南

## 一次性設定（約 5 分鐘）

### 1. 安裝 Fly CLI
```bash
# Windows (PowerShell)
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"

# 或 Linux/Mac
curl -L https://fly.io/install.sh | sh
```

### 2. 登入 Fly.io
```bash
fly auth login
```
（會開啟瀏覽器，用 GitHub 帳號登入即可）

### 3. 創建 app（一次性）
```bash
cd D:\CryptoHelper
fly apps create crypto-scanner --org personal
```

### 4. 創建 volume（一次性）
```bash
fly volumes create scanner_data --region sin --size 1
```

### 5. 設定 Secrets
```bash
fly secrets set TELEGRAM_BOT_TOKEN=你的token
fly secrets set TELEGRAM_CHAT_ID=你的chatid
```

### 6. 部署！
```bash
fly deploy
```

---

## 完成後

- ✅ Scanner 會 24/7 運行
- ✅ 每 15 分鐘自動掃描
- ✅ 有訊號時發送 Telegram 通知

## 管理指令

```bash
# 查看 logs
fly logs

# 查看狀態
fly status

# 重新部署（修改 code 後）
fly deploy

# 停止（節省費用）
fly scale count 0

# 重新啟動
fly scale count 1
```

## 費用

- **免費額度**：256MB RAM + 3GB storage
- 超過才收費（這個 app 不會超過）

---

## 故障排除

如果部署失敗，執行：
```bash
fly logs
```
查看錯誤訊息
