# Equilibrium 开发对话记录

## 日期: 2026-02-27

### 主要任务

1. **V3架构固化**
   - 统一回测和实盘逻辑
   - 使用 core/trader.py + executor.py
   - 修复加仓次数限制问题
   - 7年回测: +9160%
   - 1年回测: +1721%

2. **资金划转功能**
   - 添加 transfer 方法到 okx_client.py
   - 支持统一账户模式 (from=18, to=6)
   - 测试通过

3. **API权限确认**
   - OKX API权限: read_only, trade 即可
   - 统一账户模式无需额外权限

4. **文档维护**
   - README.md 更新
   - VERSION.md 更新
   - 编程日志.md 更新
   - PROJECT_STRUCTURE.md 新增

### 关键修复

- 去除加仓次数限制（3次→不限制）
- 修复资金划转API端点 (/api/v5/asset/transfer)
- 验证回测结果一致性

### GitHub

https://github.com/Whale-Talk/Equilibrium

### 部署命令

```bash
# 克隆
git clone https://github.com/Whale-Talk/Equilibrium.git

# 部署
cd Equilibrium
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 运行
python main.py --backtest --days 365  # 回测
python main.py --live                   # 实盘
```
