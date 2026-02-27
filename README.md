# Equilibrium - BTC 量化交易系统

## v3.0 新架构

 Equilibrium 是基于技术指标的量化交易系统，采用新架构：
- **核心逻辑**（trader.py）- 信号分析、持仓管理
- **执行层**（executor.py）- 回测/实盘分离

## 核心特性

- **趋势判断**: 基于MA20斜率判断市场趋势
- **技术指标**: RSI/MACD/布林带/ATR/ADX
- **信号过滤**: 只在趋势明显的市场中交易
- **移动止损**: 止盈后止损移至保本
- **分批止盈**: TP1=1.5倍, TP2=3倍
- **加仓策略**: 同向信号加仓，反向信号平仓
- **每月提取收益**: 余额超过100U时提取
- **爆仓保护**: 止损始终先于爆仓触发

## 运行命令

```bash
# 回测
python main.py --backtest --days 365

# 实盘
python main.py --live

# 单次分析
python main.py --once
```

## 回测结果

### 7年回测 (2019-2025)

| 版本 | 总收益 | 交易次数 |
|------|--------|----------|
| **v3.0** ⭐ | **+9160%** | 1440 |
| moderate | +9160% | 1440 |
| original | +8405% | 1440 |

### 1年回测 (2025)

| 指标 | 结果 |
|------|------|
| 初始资金 | 100U |
| **总收益** | **+1721%** |
| 交易次数 | 180次 |
| 胜率 | 45% |

## 架构

```
main.py (入口)
    ↓
core/trader.py (核心交易逻辑)
    ↓
core/executor.py (执行层)
    ├── BacktestExecutor (回测)
    └── LiveExecutor (实盘)
```

## 数据说明

- 数据来源: OKX API + 本地SQLite
- 时间范围: 2019-01-01 ~ 2026-02-26
- 数据量: 62000+根1小时K线

---

## 部署指南

### 1. 环境要求
- Python 3.8+
- SQLite

### 2. 快速部署

```bash
# 克隆项目
git clone https://github.com/Whale-Talk/Equilibrium.git
cd Equilibrium

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入API密钥
```

### 3. 运行模式

```bash
# 回测（指定天数）
python main.py --backtest --days 365          # 最近1年
python main.py --backtest --days 2555           # 7年完整回测
python main.py --backtest --days 60 --version moderate  # 特定策略

# 实盘交易
python main.py --live

# 单次分析（不执行交易）
python main.py --once
```

### 4. 策略版本

| 版本 | 说明 |
|------|------|
| `original` | 原始策略 |
| `moderate` | 温和风控（推荐） |
| `dynamic` | 动态切换 |

### 5. 环境变量 (.env)

```env
# OKX API（实盘必需）
OKX_API_KEY=your_api_key
OKX_SECRET=your_secret
OKX_PASSPHRASE=your_passphrase

# 模拟盘/回测（可选）
OKX_PAPER_TRADING=true

# Telegram通知（可选）
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 6. 目录结构

```
Equilibrium/
├── main.py                    # 入口
├── config/
│   └── config.py              # 配置
├── core/
│   ├── trader.py              # 核心交易逻辑
│   ├── executor.py            # 执行层（回测/实盘）
│   ├── okx_client.py          # OKX API
│   ├── data_manager.py        # 数据管理
│   └── trade_executor.py      # 交易执行
├── utils/
│   └── indicators.py         # 技术指标
└── data/
    └── btc_data.db            # K线数据
```

---

## 核心参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 杠杆 | 10x | |
| 风险比例 | 2% | 单笔最大风险 |
| 持仓超时 | 12h | |
| 止损 | 2×ATR | |
| 第一档止盈 | 1.5×SL | 触发后止损移至保本 |
| 第二档止盈 | 3.0×SL | 全部平仓 |

---

*更新日期: 2026-02-27*
