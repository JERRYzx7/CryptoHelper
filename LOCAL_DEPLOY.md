# 🖥️ 本地部署指南（持續運行模式）

## 🚀 快速開始

### 1. 確認環境
- ✅ Python 3.10+ 已安裝
- ✅ 依賴套件已安裝（`pip install -e .` 或已完成）
- ✅ `config.yaml` 中的 Telegram 設定正確

### 2. 啟動 Scanner
```
雙擊 start.bat
```

就這麼簡單！視窗會顯示即時 log，Scanner 開始每 15 分鐘自動掃描。

---

## 📱 使用體驗

### 啟動時
```
═══════════════════════════════════════
  🚀 CryptoHelper 加密貨幣掃描器
═══════════════════════════════════════

✅ Scanner 正在啟動...
📊 每 15 分鐘自動掃描幣安期貨
💬 有訊號時自動發送 Telegram 通知

⚠️  關閉此視窗將停止掃描
═══════════════════════════════════════

[INFO] Crypto Scanner starting…
[INFO] Enabled strategies: 6
[INFO] ═══ Scan cycle started ═══
```

### 運行中
- 每 15 分鐘自動掃描
- Log 即時顯示在視窗中
- 有訊號時立即發送 Telegram 通知
- 視窗標題顯示「運行中」提醒

### 停止
- 直接關閉視窗即可
- 或按 `Ctrl+C` 優雅退出

---

## 💡 優點

- ✅ **完全免費** - 不需雲端服務
- ✅ **不會被封鎖** - 使用你的家用網路 IP
- ✅ **即時可見** - Log 清楚顯示掃描狀態
- ✅ **完全控制** - 要用才開，不用就關
- ✅ **資料本地化** - `data/state.json` 儲存在本地

---

## 🔧 進階設定

### 開機自動啟動（選用）

如果想讓 Scanner 在電腦開機時自動啟動：

1. 按 `Win+R`，輸入 `shell:startup`
2. 在開啟的資料夾中建立 `start.bat` 的捷徑
3. 下次開機時會自動啟動 Scanner

### 修改掃描間隔

編輯 `config.yaml`：
```yaml
scanner:
  scan_interval_minutes: 30  # 改成 30 分鐘
```

### 查看歷史 Log

程式會在 console 顯示 log，如果想記錄到檔案：
```batch
python -m src.main > logs.txt 2>&1
```

---

## 🆘 故障排除

### 雙擊 start.bat 視窗閃退？
1. 用 PowerShell 測試：
   ```powershell
   cd D:\CryptoHelper
   python -m src.main
   ```
2. 查看錯誤訊息

### Python 找不到？
- 確認 Python 已加入 PATH：
  ```powershell
  python --version
  ```
- 或修改 `start.bat`，使用完整路徑：
  ```batch
  C:\Python313\python.exe -m src.main
  ```

### 沒收到 Telegram 通知？
1. 檢查 `config.yaml` 中的設定
2. 手動測試一次掃描，查看 log
3. 確認當前市場有符合條件的訊號

### 想在背景隱藏視窗運行？
建立 VBS 腳本 `start_hidden.vbs`：
```vbscript
CreateObject("Wscript.Shell").Run "D:\CryptoHelper\start.bat", 0, False
```
雙擊 VBS 就會在背景執行（無視窗）

---

## 📊 預期行為

- ✅ 啟動後立即執行一次掃描
- ✅ 之後每 15 分鐘自動掃描
- ✅ 有新訊號時發送 Telegram 通知
- ✅ 狀態儲存在 `data/state.json`
- ✅ 不會重複發送相同訊號（cooldown 機制）

---

## ⚙️ 系統需求

- **作業系統**: Windows 10/11
- **Python**: 3.10+
- **網路**: 需要連線到 Binance API 和 Telegram
- **電腦狀態**: Scanner 僅在電腦開機且程式運行時工作

---

*最後更新: 2026-04-08*
*部署方式: 本地持續運行（取代 Windows 排程）*

