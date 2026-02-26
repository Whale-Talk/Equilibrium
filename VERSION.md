# BTC3.0 版本说明

## 分支结构

| 分支 | 说明 |
|------|------|
| `master` | 稳定版 v2.3 - 推荐moderate策略 |
| `v2.0` | 原始v2策略 (+594%) |
| `v2.1-improve` | 改进版分支 |

## 标签

| 标签 | 版本 | 年化收益 | 说明 |
|------|------|----------|------|
| `v2.0-original` | v2.0 | +594% | 原始策略 |
| `v2.3-moderate` | v2.3 | +618% | 推荐策略（推荐使用） |

## 策略版本说明

### v2.0 (original)
- 原始v2策略
- 季度表现：Q1+234%, Q2+61%, Q3-48%, Q4+610%
- 全年: +594%

### v2.1 (improve_both)
- 联合改进版本
- 季度表现：Q1-3%, Q2+83%, Q3+25%, Q4+131%
- 全年: -33%
- **问题**: 严重损害趋势市收益

### v2.2 (dynamic)
- 动态切换策略
- 根据ADX和MA20斜率判断市场状态
- 全年: +549%
- 接近原始但Q4下降明显

### v2.3 (moderate) ⭐推荐
- 温和风控策略
- ADX<25时仓位减半+禁止加仓
- 季度表现：Q1+273%, Q2+73%, Q3-48%, Q4+585%
- **全年: +618%，超越原始v2！**
- 推荐作为默认策略

## 使用方法

```bash
# 推荐：moderate策略全年回测
python main.py --backtest --days 365 --version moderate

# 原始v2全年回测
python main.py --backtest --days 365 --version original

# 按季度测试
python main.py --backtest --days 365 --version moderate --quarter Q3
```

---

*最后更新: 2026-02-26*
