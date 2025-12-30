# 因子IC评估系统使用指南

## 📋 概述

这是一套完整的因子IC（Information Coefficient）评估系统，用于：
- 评估因子的预测能力
- 识别和淘汰无效因子
- 持续监控因子健康状况
- 优化因子组合

## 🎯 快速开始

### 方式1：一键运行完整评估

```bash
# 在项目根目录运行
python src/factors/run_ic_evaluation.py

# 可选参数：
# --days 60        # 数据收集天数（默认60）
# --window 60      # 评估窗口大小（默认60）
# --no-cache       # 不使用缓存，重新收集数据
# --symbols 000001.SZ 600519.SH  # 指定股票列表
```

**输出文件**：
- `factor_cache/ic_evaluation/factor_report_YYYYMMDD.md` - Markdown报告
- `factor_cache/ic_evaluation/factor_report_YYYYMMDD.json` - JSON报告
- `factor_cache/factor_history/factor_values.pkl` - 因子值历史
- `factor_cache/factor_history/returns.pkl` - 收益率历史

### 方式2：分步骤执行

```python
from src.factors.run_ic_evaluation import FactorICEvaluationPipeline

# 创建流水线
pipeline = FactorICEvaluationPipeline()

# 步骤1：收集数据
pipeline.step1_collect_data(
    symbols=['000001.SZ', '600519.SH', '000002.SZ'],
    days=60,
    use_cache=True
)

# 步骤2：计算IC
pipeline.step2_calculate_ic()

# 步骤3：评估因子
results = pipeline.step3_evaluate_factors(window=60)

# 步骤4：生成报告
report_path = pipeline.step4_generate_report(results)
```

## 📊 评估结果解读

### 因子评级

| 评级 | IC均值范围 | 含义 | 建议 |
|-----|-----------|------|------|
| A+ | IC > 0.10 | 卓越 | 提高权重 +30% |
| A | 0.08 - 0.10 | 优秀 | 提高权重 +20% |
| B | 0.05 - 0.08 | 良好 | 保持当前权重 |
| C | 0.02 - 0.05 | 一般 | 降低权重 -20% |
| D | 0 - 0.02 | 较差 | 考虑淘汰 |
| F | IC < 0 | 失效 | 立即淘汰 |

### 关键指标说明

- **IC均值**：因子预测能力的平均值
  - IC > 0.05：有效因子
  - IC > 0.10：优秀因子
  - IC < 0.02：无效因子

- **ICIR**（IC信息比率）：IC均值 / IC标准差
  - ICIR > 1.0：稳定性好
  - ICIR < 0.5：不稳定

- **IC胜率**：IC > 0 的比例
  - 胜率 > 60%：预测一致性好
  - 胜率 < 50%：不稳定

## 🔧 高级用法

### 1. 自定义数据收集

```python
from src.factors.factor_data_collector import FactorDataCollector

collector = FactorDataCollector()

# 方式A：从回测结果加载
collector.load_from_backtest_results("backtest_results")

# 方式B：模拟数据收集
from src.factors.factor_manager import FactorManager
factor_manager = FactorManager()

collector.simulate_data_collection(
    symbols=['000001.SZ', '600519.SH'],
    days=60,
    factor_manager=factor_manager
)

# 保存数据
collector.save_to_disk()
```

### 2. 单独使用IC评估器

```python
from src.factors.factor_ic_evaluator import FactorICEvaluator

evaluator = FactorICEvaluator()

# 计算单日IC
factor_values = {'000001.SZ': 0.65, '600519.SH': 0.42}
next_returns = {'000001.SZ': 0.012, '600519.SH': -0.008}

ic = evaluator.calculate_daily_ic(factor_values, next_returns, '2025-01-29')

# 更新IC历史
evaluator.update_ic_history('my_factor', '2025-01-29', ic)

# 评估因子
result = evaluator.evaluate_factor('my_factor', window=60)
print(result['rating'], result['recommendation'])
```

### 3. 因子监控

```python
from src.factors.factor_monitor import FactorMonitor
from src.factors.factor_ic_evaluator import FactorICEvaluator

# 创建监控器
evaluator = FactorICEvaluator()
monitor = FactorMonitor(evaluator)

# 每日健康检查
factor_names = ['pattern_recognition', 'volume_pattern']
report = monitor.daily_health_check(factor_names)

# 查看预警
results = monitor.monitor_all_factors(factor_names)
for name, health in results.items():
    if health['status'] == 'critical':
        print(f"⚠️ {name}: {health['alerts']}")
```

## 📈 典型工作流程

### 初次评估（第1天）

```bash
# 1. 运行完整评估
python src/factors/run_ic_evaluation.py --days 60

# 2. 查看报告
# 打开 factor_cache/ic_evaluation/factor_report_YYYYMMDD.md

# 3. 根据建议淘汰因子
# 修改因子管理器配置，移除D/F级因子
```

### 每日监控（第2-7天）

```python
from src.factors.factor_monitor import FactorMonitor
from src.factors.factor_ic_evaluator import FactorICEvaluator
from src.factors.factor_manager import FactorManager

# 获取所有因子
factor_manager = FactorManager()
factor_names = list(factor_manager.factors.keys())

# 每日监控
evaluator = FactorICEvaluator()
monitor = FactorMonitor(evaluator)

report_path = monitor.daily_health_check(factor_names)
print(f"监控报告: {report_path}")
```

### 每周评估（第7天）

```bash
# 重新运行完整评估（使用缓存数据）
python src/factors/run_ic_evaluation.py

# 对比本周和上周的报告
# 调整因子权重
```

## 🛠️ 故障排查

### 问题1：数据不足

```
❌ 错误: 数据收集失败，只收集到10天
```

**解决方案**：
```bash
# 增加数据收集天数
python src/factors/run_ic_evaluation.py --days 90

# 或指定更多股票
python src/factors/run_ic_evaluation.py --symbols 000001.SZ 600519.SH 000002.SZ 600036.SH
```

### 问题2：无IC历史

```
⚠️ 警告: 因子 xxx 没有IC历史数据
```

**解决方案**：
```bash
# 清除缓存，重新收集
python src/factors/run_ic_evaluation.py --no-cache
```

### 问题3：评估失败

```python
# 检查因子管理器是否正常
from src.factors.factor_manager import FactorManager

manager = FactorManager()
print(f"注册因子数: {len(manager.factors)}")
print(f"因子列表: {list(manager.factors.keys())}")
```

## 📂 文件结构

```
factor_cache/
├── ic_evaluation/
│   ├── ic_history.json              # IC历史记录
│   ├── factor_report_20250129.md    # 评估报告（Markdown）
│   └── factor_report_20250129.json  # 评估报告（JSON）
│
├── factor_history/
│   ├── factor_values.pkl            # 因子值历史
│   ├── returns.pkl                  # 收益率历史
│   └── stats.json                   # 数据统计
│
├── monitor_reports/
│   └── monitor_report_20250129.md   # 监控报告
│
└── disabled_factors/
    └── disabled_log.json            # 禁用因子日志
```

## 💡 最佳实践

### 1. 数据收集

- **初次评估**：收集60天数据（--days 60）
- **持续监控**：每日增量更新（复用缓存）
- **定期重置**：每月清理一次缓存（--no-cache）

### 2. 评估频率

- **完整评估**：每周1次
- **健康监控**：每日1次
- **紧急评估**：市场剧变时立即执行

### 3. 淘汰决策

- **立即淘汰**：IC < 0（负向）
- **考虑淘汰**：IC < 0.02 且 ICIR < 0.5
- **降权观察**：IC < 0.05 且胜率 < 50%
- **保留提权**：IC > 0.05

### 4. 预警响应

| 预警级别 | 响应措施 | 时限 |
|---------|---------|------|
| 🟡 黄色 | 密切关注，记录日志 | 1周 |
| 🟠 橙色 | 降低权重50% | 3天 |
| 🔴 红色 | 立即禁用因子 | 立即 |

## 🚀 集成到主系统

在主分析流程中使用IC评估结果：

```python
# main.py 或分析模块中

from src.factors.factor_ic_evaluator import FactorICEvaluator

# 初始化
evaluator = FactorICEvaluator()

# 在因子计算后，获取因子质量信息
def calculate_weighted_signal(symbol, data, factor_manager):
    # 计算所有因子
    factor_values = factor_manager.calculate_all_factors(symbol, data)

    # 根据IC评估结果调整权重
    weighted_signal = 0.0
    total_weight = 0.0

    for factor_name, factor_value in factor_values.items():
        # 获取因子统计
        stats = evaluator.get_factor_stats(factor_name)

        # 根据评级调整权重
        if stats.get('rating') == 'A+':
            weight = 1.3
        elif stats.get('rating') == 'A':
            weight = 1.2
        elif stats.get('rating') == 'B':
            weight = 1.0
        elif stats.get('rating') == 'C':
            weight = 0.8
        else:
            weight = 0.5  # D/F级降权或忽略

        weighted_signal += factor_value.value * weight
        total_weight += weight

    return weighted_signal / total_weight if total_weight > 0 else 0.0
```

## 📞 支持

如有问题，请查看：
1. 日志文件：`logs/trading_system.log`
2. IC评估日志：查看控制台输出
3. 数据统计：`factor_cache/factor_history/stats.json`
