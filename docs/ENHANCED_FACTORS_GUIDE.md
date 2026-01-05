# 增强因子系统使用指南

## 📊 系统概述

本系统新增了**10个高级因子**，并实现了**动态权重优化**和**分段验证回测**框架。

### 新增因子清单

#### 🔥 第一批：增强动量因子（4个）
1. **加速动量** (`acceleration_momentum`) - 检测动量变化率
2. **跳空缺口强度** (`gap_strength`) - 识别强势突破
3. **趋势延续性** (`trend_persistence`) - 评估趋势持续能力
4. **历史分位数** (`historical_percentile`) - 相对价值定位

#### 💰 第二批：市场微观结构因子（3个）
5. **大单资金流向** (`big_order_flow`) - 主力资金动向
6. **委买委卖比** (`bid_ask_ratio`) - 买卖意愿强度
7. **分时量比异常** (`intraday_volume_ratio`) - 交易活跃度变化

#### 😊 第三批：情绪因子（3个，支持数据缺失）
8. **龙虎榜热度** (`longhu_sentiment`) - 市场关注度
9. **社交媒体热度** (`social_media_buzz`) - 讨论热度
10. **板块联动性** (`sector_momentum`) - 板块轮动

---

## 🚀 快速开始

### 1. 初始化因子系统

```python
from src.factors.enhanced_factor_init import initialize_enhanced_factor_system

# 启用动态权重优化
init_result = initialize_enhanced_factor_system(
    enable_auto_weight_optimization=True
)

print(f"成功注册 {init_result['total_count']} 个因子")
```

### 2. 计算因子值

```python
from src.factors.factor_manager import get_factor_manager

factor_manager = get_factor_manager()

# 准备数据
symbol_data = {
    'price': price_df,  # 价格DataFrame
    'volume': volume_df  # 成交量DataFrame
}

# 计算所有因子
factor_values = factor_manager.calculate_all_factors(
    symbol='000001.SZ',
    data=symbol_data
)

# 查看结果
for factor_name, factor_value in factor_values.items():
    print(f"{factor_name}: {factor_value.value:.4f}")
```

### 3. 使用动态权重计算综合信号

```python
# 系统会自动根据IC表现调整权重
weighted_signal = factor_manager.calculate_weighted_signal(
    symbol='000001.SZ',
    data=symbol_data
)

print(f"综合信号: {weighted_signal:.4f}")
```

---

## ⚙️ 核心特性

### 1. 动态权重优化

因子权重会根据IC表现自动调整：

```python
from src.factors.enhanced_factor_init import print_factor_health_report

# 查看因子健康状况
print_factor_health_report()
```

**自动优化机制**：
- 每50次分析触发一次自动评估
- IC > 0.5 的因子会提权
- IC < 0.02 的因子会降权或淘汰
- 评级：A+ / A / B / C / D / F

### 2. 分段验证回测（处理数据缺失）

对于情绪因子等历史数据不完整的因子，使用分段验证：

```python
from src.backtest.segmented_validation import quick_validate_sentiment_factor

# 验证情绪因子（只有最近3个月数据）
result = quick_validate_sentiment_factor(
    factor_name="longhu_sentiment",
    factor_calculator=your_factor_function,
    sentiment_data_period=('2024-10-01', '2025-01-01'),  # 数据可用期
    price_data=price_data_dict,
    longhu_data=longhu_df  # 龙虎榜数据
)

print(f"推荐: {result.recommendation}")
print(f"平均IC: {result.mean_ic:.4f}")
print(f"增量夏普: {result.incremental_sharpe:.2f}")
```

### 3. 情绪因子的代理数据支持

当真实情绪数据缺失时，系统自动使用代理指标：

```python
# 龙虎榜数据缺失 -> 使用成交量异常代理
# 社交媒体数据缺失 -> 使用价格波动+成交量代理

factor_value = longhu_sentiment_factor.calculate(
    data=symbol_data,
    symbol='000001.SZ',
    longhu_data=None  # 缺失时自动使用代理
)

print(f"数据类型: {factor_value.metadata['data_type']}")  # 'proxy' 或 'real'
```

---

## 📋 使用场景

### 场景1：日常分析

```python
# 1. 初始化
from src.factors.enhanced_factor_init import enable_all_new_factors
enable_all_new_factors()

# 2. 分析股票
from src.factors.factor_manager import get_factor_manager
factor_manager = get_factor_manager()

for symbol in ['000001.SZ', '600519.SH']:
    signal = factor_manager.calculate_weighted_signal(symbol, data)
    print(f"{symbol}: {signal:.4f}")
```

### 场景2：回测验证

```python
from src.backtest.segmented_validation import SegmentedBacktestEngine

engine = SegmentedBacktestEngine()

# 定义数据可用期
data_periods = [
    ('2024-07-01', '2025-01-01', 'real'),  # 真实情绪数据期
]

result = engine.validate_factor_with_partial_data(
    factor_name="social_media_buzz",
    factor_calculator=sentiment_calculator,
    full_backtest_period=('2023-01-01', '2025-01-01'),
    data_availability_periods=data_periods,
    price_data=price_dict
)
```

### 场景3：手动权重调整

```python
from src.factors.enhanced_factor_init import (
    disable_factor_by_name,
    reset_factor_weights
)

# 手动禁用某个因子
disable_factor_by_name('social_media_buzz')

# 重置所有权重为均等
reset_factor_weights()
```

---

## 🔍 调试和监控

### 查看因子统计

```python
from src.factors.enhanced_factor_init import get_factor_summary

summary = get_factor_summary()
print(f"总因子数: {summary['total_factors']}")
print(f"活跃因子: {summary['active_factors']}")
print(f"按类别: {summary['factors_by_category']}")
```

### 查看权重配置

```python
from src.factors.factor_manager import get_factor_manager

factor_manager = get_factor_manager()

print("当前因子权重:")
for name, weight in factor_manager.factor_weights.items():
    status = "禁用" if name in factor_manager.disabled_factors else "启用"
    print(f"  {name}: {weight:.3f} ({status})")
```

---

## ⚠️ 重要注意事项

### 1. 避免过拟合

**✅ 正确做法**：
```python
# 使用分段验证，数据可用期至少3个月
data_periods = [('2024-07-01', '2025-01-01', 'real')]  # 6个月，OK
```

**❌ 错误做法**：
```python
# 数据太少，容易过拟合
data_periods = [('2024-12-01', '2025-01-01', 'real')]  # 1个月，风险高
```

### 2. 数据对齐

确保龙虎榜等数据的时间对齐：

```python
# 龙虎榜数据T日 -> 预测T+1日收益
# 系统已自动处理，但自定义数据需注意
```

### 3. 权重更新频率

```python
# 系统每50次分析自动评估一次
# 距离上次评估>7天才会触发
# 可通过 factor_manager.analysis_count 查看
```

---

## 🧪 测试

运行综合测试：

```bash
python test/test_enhanced_factor_system.py
```

测试内容：
- ✅ 新增因子计算
- ✅ 动态权重优化
- ✅ 分段验证回测
- ✅ 因子系统摘要

---

## 📚 API参考

### 初始化函数

```python
initialize_enhanced_factor_system(enable_auto_weight_optimization: bool = True) -> Dict
enable_all_new_factors() -> Dict
get_factor_summary() -> Dict
print_factor_health_report() -> None
```

### 因子管理

```python
factor_manager.calculate_all_factors(symbol, data, categories=None) -> Dict
factor_manager.calculate_weighted_signal(symbol, data) -> float
factor_manager.record_analysis_result(symbol, factor_values, next_day_return) -> None
```

### 分段验证

```python
SegmentedBacktestEngine.validate_factor_with_partial_data(
    factor_name, factor_calculator, full_backtest_period,
    data_availability_periods, price_data, **factor_data
) -> SegmentedValidationResult
```

---

## 💡 最佳实践

1. **渐进式启用**：先启用动量和微观结构因子，验证后再加情绪因子
2. **定期监控**：每周查看一次因子健康报告
3. **样本外验证**：新因子至少在3个月数据上验证后再用于实盘
4. **权重上限**：单个因子权重不超过0.25（系统默认0.5，建议调低）
5. **数据质量**：情绪数据缺失时，代理数据置信度较低（0.3-0.4）

---

## 🐛 常见问题

**Q: 为什么有些因子被自动禁用？**
A: IC评估低于阈值（mean_ic < 0.02）会自动禁用。可通过健康报告查看原因。

**Q: 如何重新启用被禁用的因子？**
A: 从 `factor_manager.disabled_factors` 中移除并调用 `_save_factor_weights()`。

**Q: 情绪因子何时使用代理数据？**
A: 当 `longhu_data` 或 `social_data` 为None或empty时自动切换。

**Q: 如何调整自动评估频率？**
A: 修改 `factor_manager.py` 中的 `if self.analysis_count % 50 == 0`。

---

## 📞 支持

如有问题，请查看：
- 日志文件: `logs/ai_factor_system.log`
- 测试脚本: `test/test_enhanced_factor_system.py`
- 因子实现: `src/factors/`
