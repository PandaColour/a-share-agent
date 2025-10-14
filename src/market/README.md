# Market Monitor Module (市场监控模块)

## 概述

市场监控模块用于监控市场整体状态，识别系统性风险，并根据市场环境调整个股投资建议。

**解决的核心问题**：
- ❌ 之前：市场大跌，系统仍然建议"持有"（只看个股不看市场）
- ✅ 现在：市场大跌，系统会根据Beta系数调整为"卖出"或"谨慎持有"

---

## 模块结构

```
src/market/
├── __init__.py              # 模块导出
├── market_state.py          # 市场状态监控
├── beta_calculator.py       # Beta系数计算
├── market_adjuster.py       # 市场调整器
└── README.md               # 本文档
```

---

## 核心功能

### 1. 市场状态监控 (`market_state.py`)

**功能**：实时监控沪深300指数，识别市场趋势和风险等级

**使用示例**：
```python
from src.market import MarketMonitor

monitor = MarketMonitor(config_manager)
market_state = monitor.get_market_state(data_provider)

print(f"市场趋势: {market_state['trend'].value}")
print(f"今日涨跌: {market_state['daily_return']:.2%}")
print(f"风险等级: {market_state['risk_level']}")
print(f"建议操作: {market_state['suggested_action']}")
```

**市场趋势分类**：
- `强势上涨` - 日涨幅 > 2%
- `温和上涨` - 日涨幅 0.5% ~ 2%
- `震荡整理` - 日涨跌幅 -0.5% ~ 0.5%
- `温和下跌` - 日跌幅 -2% ~ -0.5%
- `急跌恐慌` - 日跌幅 -4% ~ -2%
- `暴跌崩盘` - 日跌幅 < -4%

**风险等级**：
- `低` - 市场平稳
- `中` - 有一定波动
- `高` - 市场急跌或高波动
- `极高` - 市场崩盘

---

### 2. Beta系数计算 (`beta_calculator.py`)

**功能**：计算个股相对市场的系统性风险敞口

**公式**：
```
Beta = Cov(Stock_Returns, Market_Returns) / Var(Market_Returns)
```

**使用示例**：
```python
from src.market import BetaCalculator

calculator = BetaCalculator(config_manager)
beta = calculator.calculate_beta(stock_data, market_data, window=60)

print(f"Beta系数: {beta:.2f}")
print(f"分类: {calculator.classify_beta(beta)}")
print(f"描述: {calculator.get_beta_description(beta)}")
```

**Beta分类**：
- `负Beta` (< 0) - 与市场负相关，市场跌时可能涨
- `低Beta` (0 ~ 0.8) - 防御型，波动小于市场
- `中Beta` (0.8 ~ 1.2) - 市场同步
- `高Beta` (> 1.2) - 进攻型，波动大于市场

---

### 3. 市场调整器 (`market_adjuster.py`)

**功能**：根据市场状态和个股Beta调整投资建议

**调整逻辑**：

| 市场状态 | 原建议 | Beta系数 | 调整后建议 | 置信度变化 |
|---------|--------|----------|-----------|----------|
| 暴跌崩盘 | 买入 | 任意 | 持有 | +15% |
| 暴跌崩盘 | 持有 | > 1.2 (高Beta) | 卖出 | +20% |
| 暴跌崩盘 | 持有 | < 1.2 (低Beta) | 持有 | +10% |
| 急跌恐慌 | 买入 | 任意 | 持有 | +10% |
| 急跌恐慌 | 持有 | > 1.3 (超高Beta) | 卖出 | +15% |
| 温和下跌 | 买入 | > 1.2 | 买入 | -5% |
| 温和上涨 | 买入 | > 1.1 | 买入 | +8% |
| 强势上涨 | 买入 | > 1.1 | 买入 | +8% |

**使用示例**：
```python
from src.market import MarketAdjuster

adjuster = MarketAdjuster(config_manager)

# 原始建议：买入，置信度70%
# 市场状态：暴跌-3%
# 个股Beta：1.5（高Beta）

adjusted_rec, adjusted_conf, reason = adjuster.adjust_recommendation(
    original_rec="买入",
    original_confidence=0.70,
    market_state=market_state,
    stock_beta=1.5
)

# 结果：持有，置信度85%
# 理由：市场暴跌(-3.0%)，买入降级为持有
```

---

## 配置说明

在 `config/unified_config.json` 中配置：

```json
{
  "analysis_settings": {
    "market_analysis": {
      "enabled": true,
      "description": "市场相关性分析配置",

      "beta_analysis": {
        "enabled": true,
        "beta_thresholds": {
          "high_beta": 1.2,
          "low_beta": 0.8
        },
        "rolling_window": 60
      }
    }
  }
}
```

**参数说明**：
- `enabled`: 是否启用市场监控（总开关）
- `beta_thresholds.high_beta`: 高Beta阈值（默认1.2）
- `beta_thresholds.low_beta`: 低Beta阈值（默认0.8）
- `rolling_window`: Beta计算窗口天数（默认60天）

---

## 集成到决策引擎

### 完整工作流程

```python
from src.market import MarketMonitor, BetaCalculator, MarketAdjuster

# 1. 获取市场状态
monitor = MarketMonitor(config_manager)
market_state = monitor.get_market_state(data_provider)

# 2. 计算个股Beta
calculator = BetaCalculator(config_manager)
stock_beta = calculator.calculate_beta(stock_data, market_data)

# 3. 个股分析（各分析师给出建议）
recommendation = "买入"
confidence = 0.75

# 4. 市场调整
adjuster = MarketAdjuster(config_manager)
final_rec, final_conf, reason = adjuster.adjust_recommendation(
    original_rec=recommendation,
    original_confidence=confidence,
    market_state=market_state,
    stock_beta=stock_beta
)

print(f"原始: {recommendation} ({confidence:.0%})")
print(f"调整后: {final_rec} ({final_conf:.0%})")
print(f"理由: {reason}")
```

---

## 实际场景示例

### 场景1：市场大跌，高Beta股票

```python
# 市场：沪深300跌-3.5%（急跌恐慌）
# 个股：Beta = 1.6（高Beta进攻型）
# 原建议：买入（70%）

# 结果：持有（80%）
# 理由：市场急跌(-3.5%)，买入降级为持有
```

### 场景2：市场大跌，低Beta股票

```python
# 市场：沪深300跌-3.5%（急跌恐慌）
# 个股：Beta = 0.6（低Beta防御型）
# 原建议：持有（65%）

# 结果：持有（65%）
# 理由：市场下跌但Beta适中(0.60)，维持持有
```

### 场景3：市场上涨，高Beta股票

```python
# 市场：沪深300涨+2.5%（温和上涨）
# 个股：Beta = 1.4（高Beta进攻型）
# 原建议：买入（70%）

# 结果：买入（78%）
# 理由：市场上涨(+2.5%)+高Beta(1.40)，增强买入信心
```

---

## API Reference

### MarketMonitor

```python
class MarketMonitor:
    def get_market_state(data_provider, date=None) -> Dict
        """获取市场状态"""
```

**返回字段**：
- `trend`: MarketTrend枚举（市场趋势）
- `daily_return`: float（日涨跌幅）
- `returns_5d`: float（5日涨跌幅）
- `returns_20d`: float（20日涨跌幅）
- `volatility_20d`: float（20日年化波动率）
- `risk_level`: str（风险等级）
- `suggested_action`: str（建议操作）
- `confidence`: float（置信度）
- `timestamp`: str（时间戳）

### BetaCalculator

```python
class BetaCalculator:
    def calculate_beta(stock_data, market_data, window=60) -> float
        """计算Beta系数"""

    def classify_beta(beta: float) -> str
        """分类Beta：高Beta/中Beta/低Beta/负Beta"""

    def get_beta_description(beta: float) -> str
        """获取Beta描述"""
```

### MarketAdjuster

```python
class MarketAdjuster:
    def adjust_recommendation(
        original_rec: str,
        original_confidence: float,
        market_state: Dict,
        stock_beta: float
    ) -> Tuple[str, float, str]
        """调整建议，返回(建议, 置信度, 理由)"""
```

---

## 测试

创建测试文件 `test/test_market_monitor.py`：

```python
import sys
sys.path.insert(0, 'D:/github/a-share-agent')

from src.market import MarketMonitor, BetaCalculator, MarketAdjuster
from src.data.multi_source_data_provider import MultiSourceDataProvider

# 初始化
data_provider = MultiSourceDataProvider()
monitor = MarketMonitor()

# 测试市场状态
market_state = monitor.get_market_state(data_provider)
print(f"市场趋势: {market_state['trend'].value}")
print(f"风险等级: {market_state['risk_level']}")
print(f"建议操作: {market_state['suggested_action']}")
```

---

## 版本历史

### v1.0.0 (2025-09-30)
- ✅ 初始版本
- ✅ 市场状态监控
- ✅ Beta系数计算
- ✅ 市场调整器
- ✅ 完整文档

---

## 下一步计划

### 短期优化
- [ ] 支持多个市场基准（上证50、创业板指等）
- [ ] 增加行业Beta分析
- [ ] 支持自定义调整规则

### 中期优化
- [ ] 实时市场预警
- [ ] 市场情绪指标（恐慌指数VIX）
- [ ] 历史回测验证

### 长期优化
- [ ] 机器学习预测市场趋势
- [ ] 多因子市场模型
- [ ] 量化择时策略

---

## 联系方式

有问题或建议：
- 查看代码: `src/market/*.py`
- 查看配置: `config/unified_config.json`
- 运行测试: `python test/test_market_monitor.py`