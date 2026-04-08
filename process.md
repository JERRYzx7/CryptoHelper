# 📋 Crypto Scanner 開發進度回報

> 更新時間：2026-02-19 25:00（GitHub Actions + 新指標文件更新）

---

## ✅ 已完成

### 專案基礎建設
- [x] `pyproject.toml` — 專案定義、依賴管理
- [x] `config.yaml` — 所有策略參數外部化（EMA 週期、RSI 閾值、分數門檻等均可調）
- [x] `.env.example` — Telegram token 範本
- [x] `.gitignore`
- [x] 目錄結構建立（`src/`, `tests/`, 所有 `__init__.py`）

### 核心模組（所有 source code 已寫完）
| 模組 | 檔案 | 狀態 |
|------|------|------|
| Config | `src/config.py` | ✅ Pydantic v2 models + YAML 載入 + .env overlay |
| 資料抓取 | `src/data/fetcher.py` | ✅ asyncio + aiohttp + Semaphore 並發控制 + retry |
| 幣種篩選 | `src/data/market_filter.py` | ✅ Volume / 排名 / 上市天數篩選 |
| 指標計算 | `src/indicators/technical.py` | ✅ EMA / MACD / RSI / ATR / Volume MA（統一 wrapper） |
| 策略一 | `src/strategies/trend.py` | ✅ 趨勢啟動型 — EMA cross + MACD + RSI + Volume |
| 策略二 | `src/strategies/divergence.py` | ✅ 背離反轉型 — Swing low 偵測 + RSI 背離 |
| 策略三 | `src/strategies/breakout.py` | ✅ 爆量突破型 — 盤整偵測 + 突破 + 爆量 + ATR |
| 策略基底 | `src/strategies/base.py` | ✅ ABC + StrategyResult dataclass |
| 通知 | `src/notifier.py` | ✅ Telegram HTML 格式 + TradingView 連結 + retry |
| 狀態管理 | `src/state_manager.py` | ✅ JSON 去重 + cooldown + 強信號例外 |
| 排程 | `src/scheduler.py` | ✅ APScheduler 包裝 |
| 主程式 | `src/main.py` | ✅ 完整 scan loop 串接 |

### 測試
| 測試檔 | 測試數 | PASS | FAIL |
|--------|--------|------|------|
| `tests/test_indicators.py` | 9 | 9 | 0 |
| `tests/test_strategies.py` | 7 | 7 | 0 |  
| `tests/test_state_manager.py` | 14 | 14 | 0 |
| `tests/test_notifier.py` | 11 | 11 | 0 |
| **合計** | **41** | **41** | **0** |

### 依賴安裝
- [x] 所有 pip 依賴已安裝成功（`ta`, `aiohttp`, `pydantic`, `pytest` 等）

---

## ✅ 已修復

### 5. 指標測試 API 呼叫更新（2026-02-19）
切換 `ta` 套件後，`test_indicators.py` 的呼叫方式同步更新：
- `compute_ema(df, 20)` → `compute_ema(df["close"], 20)`（傳 Series）
- `compute_rsi(df)` → `compute_rsi(df["close"])`（傳 Series）
- `compute_atr(df)` → `compute_atr(df["high"], df["low"], df["close"])`（三個 Series）
- `compute_macd(df)` → `compute_macd(df["close"])` + 改驗 tuple of 3 Series
- `compute_volume_ma(df, 20)` → `compute_volume_ma(df["volume"], 20)`

### 6. StrategyWeights.total() Pydantic v2 相容性修復（2026-02-19）
- **原因**：Pydantic v2 的 `extra="allow"` 模型，extra fields 存於 `__pydantic_extra__`，不在 `__dict__`，導致 `total()` 恆回傳 0
- **修復**：`src/config.py` 的 `total()` 改用 `self.model_dump().values()` 正確取得所有 extra fields 並加總
- **影響**：`result.max_score` 現在能正確回傳如 8、9 等期望值

---

## ❌ 出錯的地方

### 1. `pandas-ta` 套件無法安裝
- **原因**：`pandas-ta` 的 PyPI distribution 壞掉，pip 找不到匹配版本
- **處理**：已切換為 `ta`（bukosabino/ta）套件，功能等價
- **影響**：`src/indicators/technical.py` 已重寫完畢，API 介面不變

### 2. Python 版本不匹配
- **原因**：`pyproject.toml` 設定 `requires-python >= 3.11`，但系統安裝的是 Python 3.10
- **處理**：已修正為 `>= 3.10`

### 3. 指標測試 3 個 FAIL（API 簽章變更）
切換 `ta` 套件後，`test_indicators.py` 的測試呼叫方式未同步更新：
- `compute_ema(df, 20)` → 現在需要 `compute_ema(df["close"], 20)`（傳 Series 而非 DataFrame）
- `compute_rsi(df)` → 同上，需傳 `df["close"]`
- `compute_atr(df)` → 現在需要三個參數 `compute_atr(df["high"], df["low"], df["close"])`

### 4. 策略測試 3 個 FAIL（enrich_dataframe 未被呼叫）
- `test_full_score` 等測試直接傳入手工建構的 DataFrame，但 `TrendStrategy.evaluate()` 需要已經 enrich 過的 DataFrame
- 測試的 mock DataFrame 缺少 `volume_ma` 等欄位的正確值
- **根因**：測試 helper 函數 `_make_trend_df` 的資料沒有正確反映策略檢查邏輯

---

## 🔲 尚未完成

1. ~~**端到端驗證**~~ ✅ GitHub Actions 已自動執行
2. ~~**Telegram 通知測試**~~ ✅ 已透過 GitHub Actions 驗證
3. **BTC 市場濾網** — Phase 3 功能，config 開關已有但 main.py 尚未串接邏輯
4. **Fly.io 實際部署** — Dockerfile + fly.toml 已建立，可選用（GitHub Actions 已提供免費替代方案）

---

## 🤖 GitHub Actions 部署指南

### Prerequisites（前置需求）

- **GitHub repository**（public 或 private 皆可）
- **Telegram Bot Token**（從 [@BotFather](https://t.me/BotFather) 取得）
- **Telegram Chat ID**（你的用戶 ID 或頻道 ID）

### Setup Steps（設定步驟）

1. **Fork 或 Clone 此 repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/CryptoHelper.git
   ```

2. **前往 Settings → Secrets and variables → Actions**
   - 在 GitHub repo 頁面點擊 `Settings` 標籤
   - 左側選單找到 `Secrets and variables` → `Actions`

3. **新增 Repository Secrets**（點擊 `New repository secret`）
   | Secret Name | Value |
   |-------------|-------|
   | `TELEGRAM_BOT_TOKEN` | 你從 @BotFather 取得的 bot token（格式：`123456789:ABCdefGHI...`） |
   | `TELEGRAM_CHAT_ID` | 你的 chat/channel ID（格式：`123456789` 或 `-100123456789`） |

4. **啟用 GitHub Actions**
   - 前往 `Actions` 標籤
   - 如果有提示，點擊 `I understand my workflows, go ahead and enable them`

5. **自動執行**
   - Scanner 會**每 15 分鐘**自動執行一次
   - 排程由 `.github/workflows/scan.yml` 的 cron 設定控制

### Manual Trigger（手動觸發）

如需立即執行掃描：

1. 前往 GitHub repo 的 **Actions** 標籤
2. 左側選擇 **"Crypto Scanner"** workflow
3. 點擊右側的 **"Run workflow"** 按鈕
4. 選擇 branch（通常是 `main`）
5. 點擊綠色的 **"Run workflow"** 確認

### Monitoring（監控）

| 監控項目 | 位置 |
|----------|------|
| 執行歷史 | `Actions` 標籤 → 選擇 workflow → 查看所有 runs |
| 通知狀態 | `data/state.json`（追蹤已通知的幣種與 cooldown） |
| 錯誤診斷 | 點擊失敗的 run → 展開 step logs |
| 即時日誌 | 點擊正在執行的 run → 查看 live output |

**常見狀態圖示：**
- ✅ 綠色勾勾：執行成功
- ❌ 紅色叉叉：執行失敗（點擊查看錯誤訊息）
- 🟡 黃色圓圈：正在執行中
- ⏸️ 灰色：已排程等待中

---

## 🆕 新增指標（v0.2）

### 新增技術指標

| 指標 | 函數 | 說明 |
|------|------|------|
| **Bollinger Bands** | `compute_bollinger_bands(close, window, num_std)` | 布林通道：中軌 SMA + 上下軌標準差帶，識別超買超賣與波動收斂 |
| **Stochastic RSI** | `compute_stoch_rsi(close, window, smooth_k, smooth_d)` | 隨機 RSI：RSI 的隨機指標化，對超買超賣更敏感 |
| **ADX** | `compute_adx(high, low, close, window)` | 平均趨向指數：量化趨勢強度（>25 有趨勢，>50 強趨勢） |
| **OBV** | `compute_obv(close, volume)` | 能量潮指標：累積成交量判斷資金流向 |

### 指標整合至策略

```python
# 趨勢策略（TrendStrategy）整合
- ADX > 25：確認趨勢存在，避免盤整假突破
- OBV 上升：確認資金流入支撐價格上漲

# 背離策略（DivergenceStrategy）整合  
- Stochastic RSI：更敏感的超買超賣偵測
- OBV 背離：價格新低但 OBV 未新低 = 潛在反轉

# 突破策略（BreakoutStrategy）整合
- Bollinger Bands 收窄：識別盤整區間
- Bollinger Bands 突破上軌 + 爆量：強勢突破訊號
- ADX 上升：突破後趨勢正在形成
```

### 使用範例

```python
from src.indicators.technical import (
    compute_bollinger_bands,
    compute_stoch_rsi,
    compute_adx,
    compute_obv
)

# Bollinger Bands
bb_upper, bb_mid, bb_lower = compute_bollinger_bands(df["close"], window=20, num_std=2)

# Stochastic RSI
stoch_k, stoch_d = compute_stoch_rsi(df["close"], window=14, smooth_k=3, smooth_d=3)

# ADX
adx = compute_adx(df["high"], df["low"], df["close"], window=14)

# OBV
obv = compute_obv(df["close"], df["volume"])
```

---

## ✅ 已完成（最新）

### 7. 智慧通知系統重構（2026-02-19）
完整取代原有純 cooldown 機制，改為「有變化才通知」的事件驅動模式。

**新增/修改：**
- `src/config.py` — `NotificationConfig` 新增 `score_delta_threshold=2`、`status_schedule_hours=[0,4,8,12,16,20]`
- `src/state_manager.py` — 新 state 格式（含 last_score）、`record(score)`、`is_active`、`get_last_score`、`invalidate`、`get_active_signals`；向下相容舊格式
- `src/notifier.py` — 新增 `format_scan_report`（三區塊格式）、`format_status_report`（定時回報）、對應 async 發送方法
- `src/scheduler.py` — 改為 cron trigger，支援 TST 固定時間排程
- `src/main.py` — scan 後分類三 bucket，只在有變化時通知；fixed-schedule 定時回報
- `tests/test_state_manager.py` — 更新至 14 個測試（含 score delta、invalidation、舊格式相容）
- `tests/test_notifier.py` — 新建 11 個格式測試

**通知邏輯：**
| 事件 | 行為 |
|------|------|
| 首次觸發 | 立即 🆕 新發現 |
| Score 提升 ≥ +2（cooldown 內）| 立即 🆕 新發現 |
| Cooldown 到期重觸 | 立即 🆕 新發現 |
| Score 降至門檻以下 | 立即 ❌ 訊號失效 |
| 0/4/8/12/16/20:00 TST（固定） | 📊 過去 4h 動態 + 持續有效 N 個 |

---

## 📁 目前專案結構

```
D:\CryptoHelper\
├── pyproject.toml
├── config.yaml
├── .env.example        # 含完整說明的範本（⚠ 複製為 .env 並填入 token）
├── .gitignore
├── .dockerignore
├── Dockerfile          # multi-stage Python 3.11-slim
├── fly.toml            # Fly.io 部署設定（nrt region, 256MB, volume）
├── project.md          # 原始計畫書
├── process.md          # ← 本檔案
│
├── .github/
│   └── workflows/
│       └── scan.yml    # GitHub Actions 自動掃描（每 15 分鐘）
│
├── data/
│   └── state.json      # 通知狀態追蹤（自動產生）
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── scheduler.py
│   ├── notifier.py
│   ├── state_manager.py
│   ├── data/
│   │   ├── fetcher.py
│   │   └── market_filter.py
│   ├── indicators/
│   │   └── technical.py
│   └── strategies/
│       ├── base.py
│       ├── trend.py
│       ├── divergence.py
│       └── breakout.py
│
└── tests/
    ├── test_indicators.py     # 9 pass
    ├── test_strategies.py     # 7 pass
    ├── test_state_manager.py  # 14 pass
    └── test_notifier.py       # 11 pass
```
