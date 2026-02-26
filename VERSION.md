# BTC3.0 版本说明

## 分支结构

| 分支 | 说明 |
|------|------|
| `master` | 稳定版 v2.0 - 原始策略 |
| `v2.1-improve` | 改进版 - 包含优化测试代码 |

## 标签

| 标签 | 版本 | 年化收益 | 说明 |
|------|------|----------|------|
| `v2.0-original` | v2.0 | +594% | 原始策略，趋势市表现好 |

## 策略版本说明

### v2.0 (master分支)
- 原始v2策略
- 季度表现：Q1+234%, Q2+61%, Q3-48%, Q4+610%
- 适合趋势明显的市场

### v2.1 (v2.1-improve分支)
- 包含入场优化和风控优化代码
- 通过 `--version` 参数选择策略：
  - `original`: 原始策略
  - `improve1`: 入场优化（RSI+MACD+成交量）
  - `improve2`: 震荡市风控（ADX判断+仓位减半+4h超时）
  - `improve_both`: 联合改进
- 通过 `--quarter` 参数按季度测试

## 使用方法

```bash
# 原始v2全年回测
python main.py --backtest --days 365 --version original

# 原始v2 Q3回测
python main.py --backtest --days 365 --version original --quarter Q3

# 联合改进全年回测
python main.py --backtest --days 365 --version improve_both
```

---

*最后更新: 2026-02-26*
