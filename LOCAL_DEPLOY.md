# 🖥️ 本地部署指南（Windows 排程）

## 優點
- ✅ 完全免費
- ✅ 不會被 Binance 封鎖
- ✅ 使用自己的網路 IP
- ✅ 資料儲存在本地（更安全）

---

## 📋 一次性設定（5 分鐘）

### 1. 確認環境變數（已設定好）
檢查 `config.yaml` 中的 Telegram 設定是否正確

### 2. 測試執行
```powershell
cd D:\CryptoHelper
python -m src.main --single-run
```
應該會掃描並在有訊號時發送 Telegram 通知

### 3. 設定 Windows 工作排程器

#### 方法 A：使用圖形介面（推薦）

1. **開啟工作排程器**
   - 按 `Win + R`
   - 輸入 `taskschd.msc`
   - 按 Enter

2. **建立新工作**
   - 右側點擊「建立工作」（不是「建立基本工作」）
   
3. **一般設定**
   - 名稱：`CryptoHelper Scanner`
   - 描述：`每15分鐘掃描加密貨幣交易訊號`
   - ☑️ 勾選「使用最高權限執行」
   - 設定：Windows 10

4. **觸發程序**
   - 點擊「新增」
   - 開始工作：「依照排程」
   - 設定：每天
   - 重複工作間隔：**15 分鐘**
   - 持續時間：**1 天**
   - ☑️ 勾選「已啟用」
   - 點擊「確定」

5. **動作**
   - 點擊「新增」
   - 動作：啟動程式
   - 程式或指令碼：`D:\CryptoHelper\run_scanner.bat`
   - 點擊「確定」

6. **條件**
   - ☐ 取消勾選「只有在電腦使用 AC 電源時才啟動工作」
   - ☐ 取消勾選「電腦改用電池電源時停止」

7. **設定**
   - ☑️ 勾選「如果工作失敗，依照下列設定重新啟動」
   - 嘗試重新啟動：3 次
   - 點擊「確定」完成

#### 方法 B：使用 PowerShell（快速）

複製以下指令到 PowerShell（**以系統管理員身分執行**）：

```powershell
$action = New-ScheduledTaskAction -Execute "D:\CryptoHelper\run_scanner.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 1)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -RunLevel Highest

Register-ScheduledTask -TaskName "CryptoHelper Scanner" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "每15分鐘掃描加密貨幣交易訊號"

Write-Host "✅ 排程已建立！" -ForegroundColor Green
Write-Host "Scanner 將從現在開始每 15 分鐘執行一次" -ForegroundColor Cyan
```

---

## ✅ 驗證

### 手動觸發測試
1. 開啟工作排程器
2. 找到「CryptoHelper Scanner」
3. 右鍵點擊 → 「執行」
4. 檢查是否收到 Telegram 通知（如果有訊號）

### 查看執行歷史
1. 工作排程器中選擇你的工作
2. 下方「歷程記錄」標籤
3. 可以看到每次執行的時間和結果

### 查看錯誤 log
```powershell
cd D:\CryptoHelper
Get-Content logs.txt -Tail 20
```

---

## 🔧 管理

### 暫停掃描
```powershell
Disable-ScheduledTask -TaskName "CryptoHelper Scanner"
```

### 恢復掃描
```powershell
Enable-ScheduledTask -TaskName "CryptoHelper Scanner"
```

### 刪除排程
```powershell
Unregister-ScheduledTask -TaskName "CryptoHelper Scanner" -Confirm:$false
```

### 修改間隔時間
如果想改成 30 分鐘：
1. 工作排程器 → 右鍵你的工作 → 內容
2. 觸發程序 → 編輯
3. 修改「重複工作間隔」
4. 確定

---

## 💡 注意事項

### 電腦需要開機
- Scanner 只在電腦開機時運作
- 如果電腦關機，排程會跳過該時段
- 開機後會自動恢復執行

### 確保 Python 在 PATH 中
測試：
```powershell
python --version
```
應該顯示 Python 版本

### 網路連線
- 確保電腦有網路連線
- 如果使用 VPN，確保 VPN 穩定

---

## 📊 預期行為

- ✅ 每 15 分鐘自動掃描
- ✅ 有訊號時發送 Telegram 通知
- ✅ 狀態儲存在 `data/state.json`
- ✅ 錯誤記錄在 `logs.txt`
- ✅ 不會重複發送相同訊號（除非訊號強度提升）

---

## 🆘 故障排除

### 排程沒執行？
1. 檢查工作排程器中的「上次執行結果」
2. 確認「下次執行時間」是否正確
3. 檢查 `logs.txt` 是否有錯誤

### 沒收到通知？
1. 手動執行測試：`python -m src.main --single-run`
2. 檢查 `config.yaml` 中的 Telegram 設定
3. 確認當前市場有符合條件的訊號

### Python 找不到？
在 `run_scanner.bat` 中使用完整路徑：
```batch
C:\Python313\python.exe -m src.main --single-run
```
