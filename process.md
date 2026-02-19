# 📋 Crypto Scanner 開發進度回報

> 更新時間：2026-02-19 24:08（智慧通知系統重構完成）

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

1. **端到端驗證** — 實際連接 Binance API 抓取資料跑一輪掃描（需 `.env`）
2. **Telegram 通知測試** — 需要設定真實的 bot token + chat ID
3. **BTC 市場濾網** — Phase 3 功能，config 開關已有但 main.py 尚未串接邏輯
4. **Fly.io 實際部署** — Dockerfile + fly.toml 已建立，尚未 `fly launch`

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
c:\crypto_helper\
├── pyproject.toml
├── config.yaml
├── .env.example        # 含完整說明的範本（⚠ 複製為 .env 並填入 token）
├── .gitignore
├── .dockerignore
├── Dockerfile          # multi-stage Python 3.11-slim
├── fly.toml            # Fly.io 部署設定（nrt region, 256MB, volume）
├── project.md              # 原始計畫書
├── process.md              # ← 本檔案
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
    ├── test_indicators.py     # 6 pass / 3 fail
    ├── test_strategies.py     # 4 pass / 3 fail
    └── test_state_manager.py  # 8 pass / 0 fail
```
