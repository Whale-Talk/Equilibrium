# Equilibrium - BTC 量化交易系统

## 项目结构

```
Equilibrium/
├── main.py                    # 主入口
├── config/
│   └── config.py              # 配置
├── core/                      # 核心模块
│   ├── trader.py              # 核心交易逻辑 (V3)
│   ├── executor.py            # 执行器接口 (V3)
│   │   ├── BacktestExecutor  # 回测执行器
│   │   └── LiveExecutor       # 实盘执行器
│   ├── okx_client.py          # OKX API客户端
│   ├── trade_executor.py      # 交易执行器
│   ├── data_manager.py        # 数据管理
│   └── notification.py        # 通知
├── utils/
│   └── indicators.py          # 技术指标
├── tests/                     # 测试
│   ├── test_backtest.py
│   ├── test_strategy.py
│   └── test_years.py
└── data/                      # 数据
    └── btc_data.db
```

## 核心文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 入口，支持回测/实盘 |
| `core/trader.py` | 核心交易逻辑（信号分析、持仓管理）|
| `core/executor.py` | 执行器抽象层 |
| `core/okx_client.py` | OKX API封装 |
| `core/trade_executor.py` | 实盘交易执行 |
| `utils/indicators.py` | 技术指标计算 |

## 运行命令

```bash
# 回测
python main.py --backtest --days 365

# 实盘
python main.py --live

# 单次分析
python main.py --once
```

---

*更新日期: 2026-02-27*
