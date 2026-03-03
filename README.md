# Equilibrium - BTC 量化交易系统

## v4.0 最新稳定版

 Equilibrium 是基于技术指标的量化交易系统，采用新架构：
- **核心逻辑**（trader.py）- 信号分析、持仓管理
- **执行层**（executor.py）- 回测/实盘分离

## 项目结构

```
Equilibrium/
├── main.py                    # 主入口
├── config/
│   └── config.py              # 配置
├── core/                      # 核心模块
│   ├── trader.py              # 核心交易逻辑
│   ├── executor.py            # 执行器接口
│   ├── okx_client.py          # OKX API客户端
│   ├── trade_executor.py      # 交易执行器
│   ├── data_manager.py        # 数据管理
│   ├── notification.py        # Telegram通知
│   └── logger.py              # 日志功能
├── utils/
│   └── indicators.py          # 技术指标
└── tests/                     # 测试
```

## 核心特性

- **趋势判断**: 基于MA20斜率判断市场趋势
- **技术指标**: RSI/MACD/布林带/ATR/ADX
- **信号过滤**: 只在趋势明显的市场中交易
- **移动止损**: 止盈后止损移至保本
- **分批止盈**: TP1=1.5倍, TP2=3倍
- **加仓策略**: 同向信号加仓，反向信号平仓
- **每月提取收益**: 余额超过100U时提取
- **爆仓保护**: 止损始终先于爆仓触发

## Telegram通知

支持交互式命令查询系统状态：

| 命令 | 功能 |
|------|------|
| 帮助 | 显示所有命令 |
| 状态 | 系统状态、价格、持仓 |
| 价格 | 当前BTC价格 |
| 余额 | 账户余额 |
| 仓位 | 当前持仓详情 |
| 信号 | 手动分析信号 |
| 交易 | 最近交易记录 |
| 统计 | 交易统计数据 |

### 通知时机

| 时机 | 说明 |
|------|------|
| 启动时 | 程序启动 + 存活确认(10s/1min/5min) |
| 每小时 | 分析报告（价格、指标） |
| 每日9点 | 每日报告 |
| 每周一9点 | 每周报告 |
| 开仓时 | 交易信号 |
| 平仓时 | 交易结果 |
| 异常时 | 系统错误/报警 |

## 运行命令

```bash
# 回测（默认original策略）
python main.py --backtest --days 365

# 回测（指定策略）
python main.py --backtest --days 365 --version moderate

# 实盘（默认original策略）
python main.py --live

# 实盘（指定策略）
python main.py --live --version moderate

# 单次分析
python main.py --once
```

## 回测结果

### 7年回测 (2019-2026)

| 版本 | 总收益 | 交易次数 | 胜率 |
|------|--------|----------|------|
| **v4.0 / moderate** ⭐ | **+10346%** | 1468 | 41.5% |
| original | +10238% | 1468 | 41.5% |
| dynamic | +9491% | 1585 | 44.2% |

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

- 数据来源: K目录数据库（/home/mjy/AI量化/K/data/btc_klines.db）
- 时间范围: 2019-01-01 ~ 2026-03
- 数据量: 62000+根1小时K线
- 架构：K文件负责数据收集，Equilibrium只负责交易

---

## 部署指南

### 1. 环境要求
- Python 3.8+
- SQLite
- Windows / Linux / Mac

### 2. 快速部署

```bash
# 克隆项目
git clone https://github.com/Whale-Talk/Equilibrium.git
cd Equilibrium

# 创建虚拟环境
python3 -m venv venv
call venv\Scripts\activate.bat  # Windows
# source venv/bin/activate      # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env 填入API密钥
```

### 3. Windows 24小时运行

#### 方法1: 使用nssm（推荐）
```powershell
# 1. 下载nssm: https://nssm.cc/download
# 2. 安装服务
nssm install Equilibrium "C:\path\to\venv\Scripts\python.exe" "C:\path\to\Equilibrium\main.py" --live

# 3. 启动服务
nssm start Equilibrium
```

#### 方法2: 使用任务计划程序
```powershell
# 1. 创建批处理文件 run.bat
@echo off
cd /d C:\path\to\Equilibrium
call venv\Scripts\activate.bat
python main.py --live

# 2. 添加计划任务（每5分钟检查）
schtasks /create /tn "Equilibrium" /tr "C:\path\to\run.bat" /sc minute /mo 5
```

#### 方法3: 使用PM2 (需要WSL或Git Bash)
```bash
# 在Git Bash或WSL中运行
pm2 start main.py -- --live
pm2 save
pm2 startup
```

#### 方法4: Linux/WSL 后台运行

```bash
# 方法1: nohup（推荐简单）
nohup python main.py --live > output.log 2>&1 &

# 方法2: screen（可重新连接）
screen -S trading
python main.py --live
# 按 Ctrl+A 然后按 D 退出screen

# 方法3: tmux
tmux new -s trading
python main.py --live
# 按 Ctrl+B 然后按 D 退出tmux
```

### 4. 运行模式

```bash
# 回测（指定天数，默认original策略）
python main.py --backtest --days 365          # 最近1年
python main.py --backtest --days 2555           # 7年完整回测
python main.py --backtest --days 60 --version moderate  # 特定策略

# 实盘交易
python main.py --live
python main.py --live --version moderate       # 指定温和策略
python main.py --live --version dynamic         # 指定动态策略

# 单次分析（不执行交易）
python main.py --once
```

### 5. 实盘配置

修改 `config/config.py`:
```python
DRY_RUN = False  # 改为False启用实盘
```

### 6. 策略版本

| 版本 | 说明 | 适合人群 |
|------|------|----------|
| `original` (默认) | 激进型，不限制加仓和持仓时间 | 追求高收益 |
| `moderate` | 温和型，震荡市场仓位减半，禁止加仓 | 稳健型投资者（推荐） |
| `dynamic` | 智能型，根据趋势强度动态调整 | 自动化交易 |

### 6. 环境变量 (.env)

```env
# OKX API（实盘必需）
OKX_API_KEY=your_api_key
OKX_SECRET_KEY=your_secret_key
OKX_PASSPHRASE=your_passphrase

# 模拟盘/回测（可选）
OKX_PAPER_TRADING=true

# Telegram通知（可选）
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# 交易配置
DRY_RUN=false           # false=实盘, true=模拟
POSITION_SIZE=10         # 仓位大小(USDT)
LEVERAGE=10             # 杠杆倍数
```

### 7. 代理配置

> ⚠️ 重要：如果无法访问OKX，需要配置代理

默认代理: `http://127.0.0.1:7897`

修改位置：
- `core/okx_client.py` - 第158-160行
- `main.py` - 第7-12行

如使用其他代理，请修改相应地址。

### 8. OKX API 权限要求

| 权限 | 说明 |
|------|------|
| 交易 (trade) | 必需 |
| 读取 (read_only) | 必需 |
| 资金划转 | 可选（自动划转需要）|

### 9. 目录结构

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
│   ├── notification.py        # Telegram通知
│   └── logger.py              # 日志功能
├── utils/
│   └── indicators.py         # 技术指标
├── logs/                      # 日志目录
└── data/                      # 本地数据（备用）
```

### 10. 数据架构

**重要**：系统使用K目录的数据库作为数据源：
- 路径：`/home/mjy/AI量化/K/data/btc_klines.db`
- K文件负责数据收集更新
- Equilibrium只负责交易逻辑

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

## 资金划转

系统支持自动资金划转（统一账户模式）：
- **资金账户 → 交易账户**：用于开仓
- **交易账户 → 资金账户**：用于提取收益

API权限要求：`trade`（交易权限即可）

---

*更新日期: 2026-03-04*
