# main.py 使用说明

## 概述

`main.py` 现在支持三种运行模式，通过 `--mode` 参数控制：

## 运行模式

### 1. 选股模式（默认）

**用途**: 分析潜在的买入机会，从市场中选择股票并进行分析

**命令**:
```bash
python main.py
# 或
python main.py --mode select
```

**输出**:
- 分析多只潜在买入股票
- 生成 `outputs/` 目录下的分析报告
- 包含买入建议、信心度、风险等级等信息

---

### 2. 持仓分析模式 ⭐ 新功能

**用途**: 分析你当前持有的股票，提供操作建议

**命令**:
```bash
python main.py --mode hold
```

**配置文件**: `config/hold_stock.json`

**输出**:
- 控制台显示持仓分析报告
- CSV文件: `outputs/holdings_analysis_YYYYMMDD_HHMMSS.csv`

**分析内容**:
- ✅ 当前盈亏情况
- ✅ 自动计算止损价格（分阶段：0天/1-3天/-3%/3天+/-5%）
- ✅ 系统分析建议（结合AI多维度分析）
- ✅ 综合操作建议（持有/加仓/减仓/止损）

---

### 3. 完整模式

**用途**: 先分析持仓股票，再进行选股分析

**命令**:
```bash
python main.py --mode both
```

---

## 示例

### 每日检查持仓
```bash
python main.py --mode hold
```

### 寻找新买入机会
```bash
python main.py --mode select
```

### 全面分析
```bash
python main.py --mode both
```
