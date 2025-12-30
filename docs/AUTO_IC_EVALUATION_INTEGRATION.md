# 自动IC评估系统 - 集成完成

## ✅ 已完成的集成

### 1. 修改的文件

- **`src/factors/factor_manager.py`** - 添加了自动IC评估能力
- **`main.py`** - 修改AI因子分析方法使用新的加权信号

### 2. 核心改动

#### `main.py` 的 `_ai_factor_analysis()` 方法（Line 978-1068）

**之前（旧方式）**:
```python
# 只计算因子，无自动评估
factors = self.factor_manager.calculate_all_factors(symbol, symbol_data)
avg_score = np.mean(factor_scores)  # 简单平均
```

**现在（新方式）**:
```python
# 【自动IC评估集成】
# 1. 计算加权因子信号
weighted_signal = self.factor_manager.calculate_weighted_signal(symbol, symbol_data)
# ↑ 这一行会：
#   - 计算所有因子
#   - 自动记录因子值（用于IC计算）
#   - 应用IC评估后的权重
#   - 每50次分析或每7天自动触发IC评估和权重调整

# 2. 获取详细因子值（用于显示）
factors = self.factor_manager.calculate_all_factors(symbol, symbol_data)

# 3. 使用加权信号而非简单平均
avg_score = weighted_signal  # 已应用IC权重
```

## 🚀 系统如何工作

### 自动化流程

```
运行 main.py
    ↓
每次分析股票时调用 calculate_weighted_signal()
    ↓
【自动记录】因子值和收益率
    ↓
【自动触发】每50次分析 或 每7天
    ↓
【自动评估】计算IC，评估因子质量
    ↓
【自动调整】根据IC评级调整权重：
    - A+/A: 提权 (+30% 或 +20%)
    - B: 保持
    - C: 降权 (-30%)
    - D/F: 淘汰（权重=0，加入禁用列表）
    ↓
【自动保存】权重配置到 factor_cache/factor_weights.json
    ↓
下次分析时自动应用新权重
```

### 触发条件

1. **分析次数触发**: 每50次分析自动触发一次评估
2. **时间触发**: 距离上次评估超过7天时触发
3. **最小数据要求**: 至少积累20天的数据才开始评估

## 📊 用户将看到的输出

### 1. 日志中的自动评估信息

```bash
# 正常分析输出
AI因子分析完成: 000001.SZ

# 每50次分析时，会看到：
============================================================
🤖 触发自动因子评估
============================================================
✓ 计算IC完成: 45天

📊 因子权重调整:
  ⬆️ pattern_recognition: 1.00 → 1.30
  ✓ volume_pattern: 保持 1.00
  ⬇️ momentum_factor: 1.00 → 0.70
  ❌ reversal_factor: 淘汰（IC均值=-0.03）

📊 因子评级分布:
  ⭐⭐⭐⭐⭐ A+: 1个
  ⭐⭐⭐⭐   A:  1个
  ⭐⭐⭐     B:  1个
  ⭐⭐       C:  0个
  ⭐         D:  0个
  ❌         F:  1个
```

### 2. 分析结果中的权重信息

```bash
AI因子分析完成: 600519.SH
决策理由:
  - AI因子加权评分: 0.6543 (已应用IC评估权重)
  - 因子评分标准差: 0.1234
  - 有效因子数量: 3/4
  - 已分析次数: 127 次
  - 已禁用因子: 1 个
  - pattern_recognition: 0.7543 (正面贡献, 权重=1.30)
  - volume_pattern: 0.5432 (正面贡献, 权重=1.00)
  - momentum_factor: 0.3210 (正面贡献, 权重=0.70)
```

### 3. 生成的配置文件

#### `factor_cache/factor_weights.json`
```json
{
  "weights": {
    "pattern_recognition": 1.3,
    "volume_pattern": 1.0,
    "momentum_factor": 0.7,
    "reversal_factor": 0.0
  },
  "disabled": [
    "reversal_factor"
  ],
  "last_update": "2025-12-29 15:30:45"
}
```

## ❌ 不再需要手动运行的命令

### 之前需要手动执行
```bash
# 旧方式：需要手动运行评估脚本
python src/factors/run_ic_evaluation.py --days 60
```

### 现在完全自动化
```bash
# 新方式：只需要运行 main.py
python main.py

# 系统会自动：
# 1. 在分析过程中收集数据
# 2. 定期触发IC评估
# 3. 自动调整权重
# 4. 淘汰无效因子
```

## 🎯 对比：旧方式 vs 新方式

| 功能 | 旧方式 | 新方式 |
|-----|-------|-------|
| 数据收集 | 需手动运行脚本 | **自动**（每次分析时） |
| IC评估 | 需手动运行脚本 | **自动**（50次/7天） |
| 权重调整 | 需手动查看报告并修改配置 | **自动**（基于IC评级） |
| 因子淘汰 | 需手动禁用 | **自动**（IC<0 或很差） |
| 持久化 | 手动保存 | **自动**（评估后保存） |
| 用户干预 | **需要** | **不需要** |

## 🔧 高级功能

### 1. 手动查看因子健康状况

```python
from src.factors.factor_manager import get_factor_manager

factor_manager = get_factor_manager()

# 获取因子健康摘要
summary = factor_manager.get_factor_health_summary()

print(f"总因子数: {summary['total_factors']}")
print(f"禁用因子数: {summary['disabled_factors']}")
print(f"已分析次数: {summary['analysis_count']}")
print(f"数据天数: {summary['data_days']}")
print(f"上次评估: {summary['last_evaluation']}")

# 查看每个因子的状态
for factor_name, info in summary['factors'].items():
    print(f"{factor_name}:")
    print(f"  评级: {info['rating']}")
    print(f"  权重: {info['weight']}")
    print(f"  禁用: {info['disabled']}")
```

### 2. 手动触发评估（可选）

```python
# 如果想立即触发评估（而不是等50次）
factor_manager._check_and_auto_evaluate()
```

### 3. 禁用自动评估（如果需要）

```python
# 在初始化时禁用
from src.factors import FactorManager

factor_manager = FactorManager(enable_auto_evaluation=False)
```

## 📂 生成的文件结构

```
factor_cache/
├── factor_weights.json              # 因子权重配置（自动生成）
├── factor_history/
│   ├── factor_values.pkl            # 因子值历史（自动收集）
│   ├── returns.pkl                  # 收益率历史（自动收集）
│   └── stats.json                   # 数据统计摘要
├── ic_evaluation/
│   ├── ic_history.json              # IC历史记录（自动生成）
│   └── factor_report_YYYYMMDD.md   # 评估报告（自动生成）
└── monitor_reports/                 # 监控报告（可选）
```

## ⚠️ 重要提示

### 1. 数据积累期

系统需要至少**20天**的数据才能开始IC评估。在此之前：
- 所有因子权重均等（1.0）
- 不会触发自动评估
- 会在日志中看到：`数据不足20天(X天)，跳过自动评估`

### 2. 权重范围

- **最小权重**: 0.0（完全禁用）
- **初始权重**: 1.0（默认）
- **最大权重**: 2.0（最优因子）

### 3. 禁用因子

被禁用的因子（IC < 0 或很差）会：
- 权重设为 0.0
- 加入 `disabled_factors` 集合
- **不参与** `calculate_weighted_signal()` 计算
- 但仍会出现在 `factor_details` 中（标记为 `disabled: true`）

## 🎉 总结

现在你只需要：

1. **运行 main.py**
   ```bash
   python main.py
   ```

2. **系统会自动**：
   - ✅ 收集因子数据
   - ✅ 计算IC评估
   - ✅ 调整因子权重
   - ✅ 淘汰无效因子
   - ✅ 保存配置

3. **你会看到**：
   - 🔍 分析结果中显示加权评分
   - 🤖 每50次分析时触发自动评估
   - 📊 因子权重调整信息
   - ❌ 无效因子被禁用的通知

**不再需要手动运行 `run_ic_evaluation.py`！**

## 💡 建议的工作流程

### 初次使用（第1-20天）
```bash
# 正常运行，系统积累数据
python main.py
# 日志会显示：数据不足20天，跳过自动评估
```

### 达到20天后
```bash
# 系统开始自动评估
python main.py
# 第50次分析时会自动触发IC评估
# 你会看到权重调整和因子淘汰信息
```

### 长期使用
```bash
# 持续运行，系统持续优化
python main.py
# 每7天或每50次分析会自动重新评估
# 因子权重会根据实际表现动态调整
```

## 🆘 问题排查

### Q: 如何确认自动评估已启用？

查看日志开头：
```bash
✓ IC评估系统已启用（自动优化）
```

### Q: 如何知道何时会触发评估？

查看分析次数：
```bash
已分析次数: 45 次  # 距离50次还有5次
```

### Q: 评估失败怎么办？

检查日志中的错误信息，常见原因：
- 数据不足（< 20天）
- 数据质量问题（没有收益率）

### Q: 如何重置权重？

删除配置文件：
```bash
rm factor_cache/factor_weights.json
# 重启系统后会使用默认权重
```

---

**集成完成！现在系统完全自动化，无需手动干预。** 🎉
