# 🚀 Railway 部署指南（完全免費）

## 網頁介面部署（最簡單，3 分鐘完成）

### 1. 登入 Railway
前往：https://railway.app
點擊 **Login with GitHub** 登入

### 2. 部署專案
1. 點擊 **New Project**
2. 選擇 **Deploy from GitHub repo**
3. 授權 Railway 存取你的 GitHub
4. 選擇 `CryptoHelper` 倉庫
5. 點擊 **Deploy Now**

### 3. 設定環境變數
在 Railway 專案頁面：
1. 點擊你的 service
2. 選擇 **Variables** 標籤
3. 新增以下變數：
   - `TELEGRAM_BOT_TOKEN` = 你的 bot token
   - `TELEGRAM_CHAT_ID` = 你的 chat id
   - `STATE_DIR` = `/app/data`
4. 點擊 **Deploy**

### 4. 新增 Volume（持久化儲存）
1. 在 service 頁面選擇 **Settings**
2. 滾到 **Volumes** 區塊
3. 點擊 **New Volume**
4. Mount Path 填入：`/app/data`
5. 點擊 **Add**
6. **重新部署**（會自動觸發）

---

## ✅ 完成！

- Scanner 現在 24/7 運行
- 每 15 分鐘自動掃描
- 有訊號時發送 Telegram 通知

---

## 查看 Logs

在 Railway 專案頁面：
1. 點擊你的 service
2. 選擇 **Deployments** 標籤
3. 點擊最新的 deployment
4. 即時查看 logs

---

## 費用

- **免費額度**：$5 USD/月
- 你的 app 用量：~$3/月（在免費額度內）
- 超過 $5 才會要求綁卡

---

## CLI 部署方式（進階）

### 1. 安裝 Railway CLI
```bash
npm install -g @railway/cli
```

### 2. 登入
```bash
railway login
```

### 3. 部署
```bash
cd D:\CryptoHelper
railway up
```

### 4. 設定環境變數
```bash
railway variables set TELEGRAM_BOT_TOKEN=你的token
railway variables set TELEGRAM_CHAT_ID=你的chatid
railway variables set STATE_DIR=/app/data
```

### 5. 查看 logs
```bash
railway logs
```

---

## 故障排除

### Scanner 沒有發送通知？
1. 檢查 logs 確認有在掃描
2. 確認環境變數設定正確
3. 確認 volume mount 到 `/app/data`

### 想要重新部署？
```bash
railway up --detach
```

或在網頁介面點擊 **Redeploy**
