# 历史回测系统使用指南

## 📊 功能概述

历史回测系统实现了对历史数据的逐日分析和模拟交易，完全集成了AI因子分析、风险管理和选股系统。

## 🎯 核心特性

### 1. **完全复用现有系统**
- ✅ 复用选股系统（自动使用 `config/dynamic_stock.json` 或重新选股）
- ✅ 复用 AI 因子分析系统
- ✅ 复用风险管理系统
- ✅ 复用投资组合决策系统

### 2. **避免未来数据泄露**
- ✅ 对每个交易日，只使用**截至当日**的历史数据
- ✅ 模拟真实的"站在历史某一天"做分析和决策

### 3. **完整的回测指标**
- 收益指标：总收益率、年化收益率、盈亏金额
- 风险指标：年化波动率、夏普比率、最大回撤
- 交易统计：总交易次数、胜率、平均持有天数

## 🚀 使用方法

### 方式1: 回测最近N个月（最简单）

```bash
# 回测最近1个月
python main.py --mode backtest --months 1

# 回测最近3个月（默认）
python main.py --mode backtest --months 3

# 回测最近6个月
python main.py --mode backtest --months 6

# 回测最近1年
python main.py --mode backtest --months 12
```

### 方式2: 回测指定时间段

```bash
# 回测2024年9月
python main.py --mode backtest --start-date 2024-09-01 --end-date 2024-09-30

# 回测2024年Q3
python main.py --mode backtest --start-date 2024-07-01 --end-date 2024-09-30

# 回测2024年上半年
python main.py --mode backtest --start-date 2024-01-01 --end-date 2024-06-30

# 回测2024年全年
python main.py --mode backtest --start-date 2024-01-01 --end-date 2024-12-31
```

### 方式3: 使用测试脚本

```bash
# 快速测试（1个月）
python test/test_historical_backtest.py --test simple

# 指定日期测试
python test/test_historical_backtest.py --test dates

# 3个月测试
python test/test_historical_backtest.py --test 3months

# 运行所有测试
python test/test_historical_backtest.py --test all
```

## 📋 股票池选择

回测系统**自动复用**现有的选股系统：

### 情况1: `config/dynamic_stock.json` 是今天的
```python
# 系统行为
- 检测到缓存文件日期 = 今天
- ✅ 直接使用缓存的股票池
- 日志: "使用缓存的选股结果"
```

### 情况2: `config/dynamic_stock.json` 不是今天的
```python
# 系统行为
- 检测到缓存文件日期 != 今天（或不存在）
- 🔄 自动运行选股流程
- ✅ 使用新选择的股票池
- 日志: "缓存无效，执行新的动态选股"
```

**无需手动干预！** 系统会自动判断是否需要重新选股。

## 📊 输出结果

### 控制台输出

```
回测结果摘要
============================================================
回测时间范围: 2024-09-01 至 2024-12-31
回测股票数量: 25 只
交易日数量: 84 天
生成决策数: 156 条
初始资金: ¥1,000,000

收益指标:
  总收益率: +15.23%
  年化收益率: +18.76%
  最终资金: ¥1,152,300.00
  盈亏金额: ¥152,300.00

风险指标:
  年化波动率: 22.45%
  夏普比率: 0.73
  最大回撤: -8.34%

交易统计:
  总交易次数: 48 笔
  买入次数: 24 笔
  卖出次数: 24 笔
  胜率: 62.50%
  平均持有天数: 12.5 天
```

### 文件输出

回测结果保存在 `outputs/YYYYMMDD_HHMMSS/` 目录下：

```
outputs/20241231_143052/
├── backtest_results.json          # 回测摘要结果
├── backtest_trade_history.json    # 详细交易记录
└── README.md                       # 说明文档（如果有）
```

#### `backtest_results.json` 内容

```json
{
  "total_return": 0.1523,
  "annualized_return": 0.1876,
  "initial_capital": 1000000.0,
  "final_capital": 1152300.0,
  "profit": 152300.0,
  "volatility": 0.2245,
  "sharpe_ratio": 0.73,
  "max_drawdown": -0.0834,
  "total_trades": 48,
  "buy_trades": 24,
  "sell_trades": 24,
  "win_rate": 0.625,
  "avg_holding_days": 12.5,
  "backtest_config": {
    "start_date": "2024-09-01",
    "end_date": "2024-12-31",
    "stock_count": 25,
    "trading_days": 84,
    "decision_count": 156,
    "initial_capital": 1000000.0
  }
}
```

#### `backtest_trade_history.json` 内容

```json
[
  {
    "date": "2024-09-05",
    "symbol": "600519.SH",
    "action": "买入",
    "price": 1520.50,
    "shares": 600,
    "value": 912300.0,
    "cost": 1368.45,
    "total_cost": 913668.45
  },
  {
    "date": "2024-09-18",
    "symbol": "600519.SH",
    "action": "卖出",
    "price": 1585.20,
    "shares": 600,
    "value": 951120.0,
    "profit": 36503.55,
    "profit_pct": 0.0400,
    "holding_days": 13
  }
]
```

## ⚙️ 回测参数配置

回测使用 `config/unified_config.json` 中的配置：

```json
{
  "backtest_settings": {
    "capital_management": {
      "initial_capital": 1000000.0,    // 初始资金（元）
      "max_position_size": 0.15        // 单只股票最大仓位（15%）
    },
    "transaction_costs": {
      "commission_rate": 0.0015,       // 佣金率（0.15%）
      "min_commission": 5.0,           // 最低佣金（5元）
      "stamp_duty_rate": 0.001         // 印花税率（0.1%）
    }
  },
  "analysis_settings": {
    "risk_management": {
      "stop_loss_rate": -0.08,         // 止损率（-8%）
      "take_profit_rate": 0.15,        // 止盈率（+15%）
      "max_holding_days": 45           // 最大持有天数
    }
  }
}
```

## 🔍 回测流程详解

```
1. 股票池选择
   ├─ 检查 config/dynamic_stock.json
   ├─ 如果是今天的 → 使用缓存
   └─ 如果不是今天的 → 重新选股

2. 历史数据收集
   ├─ 对每只股票收集指定时间段的历史数据
   ├─ 向前扩展90天（确保有足够数据计算指标）
   └─ 过滤数据不足的股票（< 60天）

3. 逐日历史分析（关键步骤！）
   对每个交易日:
     对每只股票:
       ├─ 提取截至当日的历史数据（避免未来信息）
       ├─ 运行 AI 因子分析
       ├─ 运行风险评估
       ├─ 生成交易决策（买入/卖出/持有）
       └─ 记录买入和卖出信号

4. 回测模拟交易
   ├─ 使用现有的 AdvancedBacktestEngine
   ├─ 应用仓位管理规则
   ├─ 应用止损止盈规则
   ├─ 计算交易成本
   └─ 记录每日收益和组合价值

5. 结果分析和输出
   ├─ 计算收益指标
   ├─ 计算风险指标
   ├─ 统计交易情况
   └─ 保存结果文件
```

## 💡 使用建议

### 1. 首次使用
```bash
# 先测试1个月，确认系统正常
python main.py --mode backtest --months 1
```

### 2. 性能考虑

**回测时间估算：**
- 1个月回测：约 3-5 分钟
- 3个月回测：约 8-15 分钟
- 6个月回测：约 15-30 分钟
- 1年回测：约 30-60 分钟

**影响因素：**
- 股票数量（默认约 20-30 只）
- 网络速度（数据下载）
- AI 模型速度

### 3. 数据要求

- 需要足够的历史数据（建议至少 60 天）
- 数据源稳定性（AkShare/Tushare）
- 网络连接稳定

### 4. 结果解读

**好的回测结果：**
- ✅ 总收益率 > 10%（3个月）
- ✅ 夏普比率 > 1.0
- ✅ 最大回撤 < 15%
- ✅ 胜率 > 55%

**需要优化：**
- ❌ 总收益率 < 5%
- ❌ 夏普比率 < 0.5
- ❌ 最大回撤 > 20%
- ❌ 胜率 < 45%

## 🐛 常见问题

### Q1: 回测失败，提示"没有可用的股票"
```
A: 检查 config/dynamic_stock.json 是否存在，或手动运行一次选股：
   python main.py --mode select
```

### Q2: 回测很慢，如何加速？
```
A: 1. 减少回测时间范围（如1个月）
   2. 减少股票数量（修改选股配置）
   3. 使用更快的数据源
```

### Q3: 回测结果与实际差异大？
```
A: 这是正常的，原因：
   1. 回测使用的是收盘价，实际交易有滑点
   2. 回测假设所有订单都能成交
   3. 市场环境变化
```

### Q4: 如何只回测特定股票？
```
A: 暂不支持，但可以修改 config/hold_stock.json 并使用持仓模式
```

## 📚 技术实现

### 代码结构

```
src/backtest/
├── historical_backtest_runner.py    # 历史回测运行器（新增）
├── advanced_backtest_engine.py      # 回测引擎（复用）
└── data_collector.py                # 数据收集器（复用）

main.py                              # 添加了 backtest 模式（修改）

test/
└── test_historical_backtest.py      # 回测测试脚本（新增）
```

### 关键类

**HistoricalBacktestRunner**
- `run_historical_backtest()` - 主入口
- `_get_stock_pool()` - 复用选股系统
- `_generate_historical_recommendations()` - 逐日分析
- `_analyze_trading_day()` - 单日分析

**复用的组件**
- `StockSelectionManager` - 选股
- `AI因子分析` - 因子计算
- `RiskManager` - 风险评估
- `PortfolioManager` - 决策生成
- `AdvancedBacktestEngine` - 回测执行

## 🔄 与其他模式对比

| 模式 | 用途 | 数据 | 输出 |
|-----|------|------|------|
| `--mode select` | 选股分析 | 实时数据 | 当前建议 |
| `--mode hold` | 持仓分析 | 实时数据 | 持仓建议 |
| `--mode both` | 全面分析 | 实时数据 | 选股+持仓 |
| `--mode backtest` | 历史回测 | 历史数据 | 收益统计 |

## 🎓 下一步

1. 运行简单测试：
   ```bash
   python main.py --mode backtest --months 1
   ```

2. 分析回测结果，调整策略参数

3. 运行更长时间的回测验证策略

4. 根据回测结果优化 AI 因子或风险管理参数

---

**注意**: 回测结果仅供参考，不构成投资建议。历史表现不代表未来收益。
