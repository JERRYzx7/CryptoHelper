# 📊 Crypto 多策略技術指標掃描與通知系統計畫書

---

## 一、專案背景與目標

在數百種加密貨幣中，透過人工方式逐一檢視技術指標效率極低。本專案旨在建立一套**多策略、自動化掃描系統**，透過交易所 API 取得 K 線資料，計算多種技術指標，篩選出潛在交易機會，並透過 Telegram 發送通知。

本系統不提供直接交易建議，而是提供「潛在關注對象（Potential Setup）」供人工二次判斷。

---

## 二、專案目標

- 自動抓取交易所 USDT 永續合約 K 線資料
- 計算多種技術指標（EMA、MACD、RSI、ATR、Volume MA）
- 實作三種獨立策略模型
- 採用打分機制降低雜訊（打分邏輯內聚在各策略內）
- 避免重複通知（JSON state + cooldown + 強信號例外）
- Telegram HTML 格式分段顯示推薦理由
- 所有策略參數外部化為 YAML config，方便調參不需改 code
- 可長期擴充（SMC、Funding、OI、回測模組）

---

## 三、市場範圍設計

### 交易所
- Binance USDT Perpetual

### 幣種篩選條件
- 24h 成交量 > 20M USDT
- 排名前 200（依 24h quote volume 排序）
- 排除上市未滿 7 天幣種（依 `onboardDate` 判斷）

### 執行頻率
- 每 15 分鐘執行一次掃描

### 時間框架
- 4H（趨勢判斷）
- 1H（反轉與突破判斷）
- 15m（未來擴充）

---

## 四、策略模型設計

> 所有策略繼承共用 `BaseStrategy` ABC，各自實作 `evaluate(df) → StrategyResult(score, max_score, details)`。
> 打分邏輯**內聚於策略內部**，不使用獨立的 scoring 模組。

---

### 🟢 策略一：趨勢啟動型（Trend Initiation Model）

**時間框架：4H**

#### 條件定義

- EMA20 上穿 EMA50（黃金交叉 — 當前 bar EMA_fast > EMA_slow，且前一根 ≤）
- MACD Histogram 由負轉正（前一根 ≤ 0，當前 > 0）
- RSI > 50
- 當前成交量 > 1.5 × 20MA Volume

#### 打分機制

| 條件 | 分數 | config key |
|------|------|------------|
| EMA Cross | +3 | `strategies.trend.weights.ema_cross` |
| MACD Cross | +2 | `strategies.trend.weights.macd_cross` |
| RSI > 50 | +1 | `strategies.trend.weights.rsi_above` |
| Volume 放大 | +2 | `strategies.trend.weights.volume_surge` |

**≥ 6 分發送通知**（可由 `strategies.trend.score_threshold` 調整）

---

### 🔵 策略二：背離反轉型（Divergence Reversal Model）

**時間框架：1H**

#### 條件定義

- 價格創最近 20 根 K 線的 Swing Low（新低）
- RSI 未創新低（Bullish Divergence）
- 成交量逐步縮小
- RSI < 40（超賣區）

#### 量化細節

- **Swing Low 偵測**：前後各 `swing_window`（預設 5）根 K 線都高於該點，即局部最低
- **RSI 背離判斷**：`price[current] < price[prev_swing_low]` 且 `rsi[current] > rsi[prev_swing_low]`
- **Volume 縮小**：最近 5 根 Volume MA 均值 < 前 10 根 Volume MA 均值

#### 打分機制

| 條件 | 分數 | config key |
|------|------|------------|
| 價格新低 | +2 | `strategies.divergence.weights.price_new_low` |
| RSI 背離 | +3 | `strategies.divergence.weights.rsi_divergence` |
| Volume 縮小 | +1 | `strategies.divergence.weights.volume_decline` |
| 超賣 | +2 | `strategies.divergence.weights.oversold` |

**≥ 6 分發送通知**（可由 `strategies.divergence.score_threshold` 調整）

---

### 🟠 策略三：爆量突破型（Volume Breakout Model）

**時間框架：1H**

#### 條件定義

- 最近 24 根 K 線屬於盤整區間
- 當前收盤價突破盤整區間高點
- 成交量 > 2 × 20MA Volume
- ATR 正在擴張

#### 量化細節

- **盤整定義**：最近 `consolidation_bars`（預設 24）根 K 線的 `(highest_high - lowest_low) / lowest_low ≤ range_threshold_pct%`（預設 5%）
- **突破**：`close > consolidation_high`（盤整區間排除當前 bar，避免 look-ahead bias）
- **ATR 擴張**：`current_atr > ATR 20 期移動平均`

#### 打分機制

| 條件 | 分數 | config key |
|------|------|------------|
| 區間盤整 | +2 | `strategies.breakout.weights.consolidation` |
| 突破 | +3 | `strategies.breakout.weights.breakout` |
| 爆量 | +3 | `strategies.breakout.weights.volume_surge` |
| ATR 擴張 | +1 | `strategies.breakout.weights.atr_expansion` |

**≥ 6 分發送通知**（可由 `strategies.breakout.score_threshold` 調整）

---

## 五、BTC 市場濾網（風險過濾）

可選條件（`btc_filter.enabled` 預設 `false`，可在 config.yaml 啟用）：

- BTC 4H EMA20 > EMA50 才允許多單訊號
- 若 BTC RSI < 40，暫停多單通知
- Funding Rate 過熱（> 0.05%）則不通知

---

## 六、系統架構設計

```
c:\crypto_helper\
├── pyproject.toml              # 專案定義 + 依賴管理
├── config.yaml                 # 所有策略參數（YAML 外部化）
├── .env                        # Telegram token / API secrets
│
├── src/
│   ├── config.py               # Pydantic v2 config models + YAML 載入
│   ├── main.py                 # 入口：scan loop 串接
│   ├── scheduler.py            # APScheduler 排程
│   ├── notifier.py             # Telegram HTML 格式通知 + retry
│   ├── state_manager.py        # JSON 去重 + cooldown + 強信號例外
│   │
│   ├── data/
│   │   ├── fetcher.py          # Binance API（asyncio + aiohttp + Semaphore + retry）
│   │   └── market_filter.py    # 幣種篩選
│   │
│   ├── indicators/
│   │   └── technical.py        # 統一 ta 套件 wrapper（EMA/MACD/RSI/ATR/Volume MA）
│   │
│   └── strategies/
│       ├── base.py             # BaseStrategy ABC + StrategyResult dataclass
│       ├── trend.py            # 策略一：趨勢啟動型
│       ├── divergence.py       # 策略二：背離反轉型
│       └── breakout.py         # 策略三：爆量突破型
│
└── tests/
    ├── test_indicators.py
    ├── test_strategies.py
    └── test_state_manager.py
```

### 與原方案的架構差異

| 原方案 | 實際實作 | 原因 |
|--------|---------|------|
| `indicators/` 每個指標一個檔案 | 合併為 `technical.py` | 每個指標僅數十行，拆開太碎片化 |
| 獨立 `scoring.py` | 打分內聚在各 strategy 內 | 每個策略權重不同，分離會增加耦合 |
| 無 config 外部化 | `config.yaml` + `pydantic` 驗證 | 調參不需改 code |
| 無錯誤處理設計 | retry + heartbeat + error alert | 生產環境穩定性需求 |

---

## 七、資料處理流程

```
Scheduler (APScheduler, 每 15 分鐘)
    ↓
Fetch Market List (exchange_info + 24h tickers)
    ↓
Filter Symbols (volume / rank / listing age)
    ↓
Group Strategies by Timeframe (減少 API 請求)
    ↓
Batch Fetch Klines (asyncio + Semaphore 並發, max 10)
    ↓
Enrich DataFrame (EMA / MACD / RSI / ATR / Volume MA)
    ↓
Evaluate All Strategies → StrategyResult(score, details)
    ↓
Check State Manager (cooldown / 強信號例外)
    ↓
Send Telegram Notification (HTML 格式 + TradingView 連結)
```

---

## 八、Telegram 通知格式

```
📊 SOLUSDT

【趨勢啟動型】
Score: 8/8

  ✓ EMA20 ↑穿 EMA50
  ✓ MACD 金叉（Histogram 由負轉正）
  ✓ Volume 1.8x（>1.5x）
  ✓ RSI 56.0 > 50

【爆量突破型】
Score: 7/9

  ✓ 盤整區間 3.2%（≤5.0%）
  ✓ 收盤 24.5600 突破區間高點 24.2300
  ✓ Volume 2.4x（>2.0x）

📈 TradingView
```

---

## 九、防止重複通知機制

- 以 JSON 檔記錄每個 `{symbol}__{strategy}` 最後通知時間
- cooldown 預設 4 小時，可由 `notification.cooldown_hours` 調整
- 強信號（score ≥ `notification.strong_signal_threshold`，預設 8）可繞過 cooldown
- 不同策略、不同幣種之間 cooldown 獨立

---

## 十、錯誤處理與監控

- **API 請求**：exponential backoff retry（最多 3 次）+ `asyncio.Semaphore` 並發控制
- **Rate Limit**：收到 429 自動退避等待
- **Heartbeat**：每小時發送 Telegram 系統存活通知
- **Error Alert**：scan loop 未預期錯誤發送 Telegram 告警
- **Logging**：全域 `logging` 模組，console 輸出 + 可配置 level

---

## 十一、資料儲存與擴充設計

未來可加入：

- SQLite / PostgreSQL 記錄歷史訊號
- 自動統計 24H / 72H 後報酬率
- 回測模組
- Dashboard 視覺化
- SMC 結構判斷（OB / BOS / FVG）
- Funding / Open Interest API 整合
- WebSocket 即時 K 線（取代 REST polling）

---

## 十二、技術棧

- **語言**：Python 3.10+
- **資料處理**：pandas
- **技術指標**：ta（bukosabino/ta）
- **HTTP 請求**：aiohttp（asyncio 非同步並發）
- **Config 驗證**：pydantic v2 + PyYAML
- **排程**：APScheduler
- **通知**：python-telegram-bot v21
- **環境變數**：python-dotenv
- **測試**：pytest + pytest-asyncio
- **部署**：Docker（未來）

---

## 十三、風險聲明

- 技術指標並不保證獲利
- 僅提供潛在交易機會提示
- 需搭配人工風險控管與倉位管理

---

## 十四、開發階段規劃

### Phase 1 ✅
- 專案基礎建設（pyproject.toml, config.yaml, 目錄結構）
- 資料抓取模組（asyncio + rate limit + retry）
- 指標計算模組（ta 套件 wrapper）
- 策略一：趨勢啟動型

### Phase 2 ✅
- 策略二：背離反轉型（含量化 swing low 偵測）
- 策略三：爆量突破型（含量化盤整定義）
- Telegram 通知模組
- 打分系統（內聚於策略）

### Phase 3
- BTC 市場濾網
- 去重機制 ✅（已實作 state_manager.py）
- 錯誤處理 / Retry / Heartbeat ✅（已實作）
- 紀錄與回測

### Phase 4
- 資金流 + Funding + OI
- SMC 整合
- Dashboard
- WebSocket 即時 K 線

---

# 結論

本系統設計為「多策略 + 打分 + 市場濾網」的半量化掃描框架，
目標為降低情緒交易，建立可持續優化的交易研究系統。

所有策略參數透過 `config.yaml` 外部化管理，調參不需修改程式碼。
打分邏輯內聚在各策略模組中，保持高內聚低耦合的設計原則。

---