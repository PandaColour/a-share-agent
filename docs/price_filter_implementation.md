# 选股阶段价格过滤功能实现说明

## 功能概述

实现了在股票选择阶段就应用价格限制过滤,而不是等到分析阶段才跳过。这样可以:
- 避免浪费资源分析不符合价格要求的股票
- 提前剔除不满足条件的股票,提高系统效率
- 让用户清楚地看到哪些股票因价格被过滤掉

## 实现细节

### 1. 修改位置

文件: `src/stock/dynamic_stock_selector.py`

### 2. 核心改动

#### 2.1 新增方法: `_fetch_stock_prices()`

```python
def _fetch_stock_prices(self, candidates: List[StockCandidate]):
    """
    批量获取候选股票的实时价格

    功能:
    - 使用akshare的stock_zh_a_spot_em接口批量获取所有A股实时行情
    - 创建股票代码到价格的映射字典
    - 更新候选股票列表中的价格字段
    - 记录成功/失败统计信息
    """
```

特点:
- 批量获取,效率高(一次调用获取所有A股价格)
- 自动跳过已有价格数据的股票
- 详细的日志记录,便于调试

#### 2.2 修改方法: `_apply_filters()`

**修改前:**
```python
# 价格限制（全局）
if global_filters.get('enable_price_limits', False):
    price_min = global_filters.get('price_limit_min', 0.0)
    price_max = global_filters.get('price_limit_max', 100000.0)
    if candidate.price > 0:  # 只有当有价格数据时才应用
        if candidate.price < price_min or candidate.price > price_max:
            logger.debug(f"过滤价格超限股票: {candidate.name} (价格: {candidate.price}元)")
            continue
```

问题:
- 如果candidate.price <= 0,价格限制被忽略
- 股票会进入分析阶段,然后在分析时才跳过
- 用户看不到哪些股票因价格被过滤

**修改后:**
```python
# 在过滤之前,先批量获取价格
if enable_price_limits:
    logger.info(f"价格限制已启用: {price_min}元 - {price_max}元,开始获取股票价格...")
    self._fetch_stock_prices(candidates)

# 价格限制（全局）- 在选股阶段强制过滤
if enable_price_limits:
    if candidate.price <= 0:
        # 没有价格数据,过滤掉
        logger.info(f"过滤无价格数据股票: {candidate.name}({candidate.symbol})")
        continue
    elif candidate.price < price_min or candidate.price > price_max:
        logger.info(f"过滤价格超限股票: {candidate.name}({candidate.symbol}) (价格: {candidate.price:.2f}元, 限制: {price_min}-{price_max}元)")
        continue
```

改进:
- ✅ 主动获取价格数据
- ✅ 强制过滤无价格数据的股票
- ✅ 强制过滤价格超限的股票
- ✅ 使用logger.info而非logger.debug,让用户看到过滤信息
- ✅ 详细的过滤日志,包含具体价格和限制范围

### 3. 配置说明

在 `config/unified_config.json` 中:

```json
{
  "analysis_settings": {
    "filters": {
      "enable_price_limits": true,
      "price_limit_min": 15.0,
      "price_limit_max": 10000.0
    }
  }
}
```

- `enable_price_limits`: 是否启用价格限制
- `price_limit_min`: 最低价格(元)
- `price_limit_max`: 最高价格(元)

## 工作流程

```
1. 收集候选股票 (配置+龙虎榜+社交媒体+潜力股)
   ↓
2. 去重并排序
   ↓
3. _apply_filters() - 应用过滤器
   ├─ 检查是否启用价格限制
   ├─ 如果启用:
   │  └─ 调用 _fetch_stock_prices() 批量获取价格
   ├─ 遍历候选股票:
   │  ├─ ST股票过滤
   │  ├─ 创业板过滤
   │  ├─ **价格过滤 (NEW)**:
   │  │  ├─ 无价格数据 → 过滤
   │  │  └─ 价格超限 → 过滤
   │  ├─ 潜力股技术过滤 (RSI, 涨跌幅, 量比)
   │  └─ 评分阈值过滤
   ↓
4. 选择最终股票
   ↓
5. 返回结果
```

## 测试验证

测试脚本: `test_price_filter.py`

### 测试场景1: 价格限制启用,成功获取价格

```
配置: enable_price_limits=true, 15元-10000元
结果:
  - 获取候选股票价格 ✓
  - 过滤掉价格<15元或>10000元的股票 ✓
  - 只保留符合条件的股票 ✓
```

### 测试场景2: 价格限制启用,获取价格失败

```
配置: enable_price_limits=true, 15元-10000元
结果:
  - 尝试获取价格,但网络失败 ✓
  - 候选股票price=0 (默认值) ✓
  - 所有股票因"无价格数据"被过滤 ✓
  - 最终选择0只股票 ✓
```

这是**预期行为** - 宁可不选,也不选不符合条件的股票。

### 测试场景3: 价格限制未启用

```
配置: enable_price_limits=false
结果:
  - 不获取价格 ✓
  - 不应用价格过滤 ✓
  - 按其他过滤条件选股 ✓
```

## 日志输出示例

```
2025-10-20 10:51:41,253 - src.stock.dynamic_stock_selector - INFO - 价格限制已启用: 15.0元 - 10000.0元,开始获取股票价格...
2025-10-20 10:51:41,253 - src.stock.dynamic_stock_selector - INFO - 开始获取 6 只股票的价格数据...
2025-10-20 10:51:42,257 - src.stock.dynamic_stock_selector - WARNING - 获取实时行情数据失败,股票价格将保持默认值
2025-10-20 10:51:42,257 - src.stock.dynamic_stock_selector - INFO - 过滤无价格数据股票: 通富微电(002156.SZ)
2025-10-20 10:51:42,257 - src.stock.dynamic_stock_selector - INFO - 过滤无价格数据股票: 士兰微(600460.SH)
2025-10-20 10:51:42,257 - src.stock.dynamic_stock_selector - INFO - 过滤无价格数据股票: 三花智控(002050.SZ)
...
2025-10-20 10:51:42,257 - src.stock.dynamic_stock_selector - INFO - 过滤后剩余候选股票: 0 只
```

## 与分析阶段价格过滤的对比

### 之前的行为 (分析阶段跳过)

```python
# main.py 或 analysis_engine.py
for symbol, name in stocks:
    current_price = get_price(symbol)
    if current_price < price_min or current_price > price_max:
        logger.info(f"跳过价格不符合的股票: {name}")
        continue  # 跳过分析

    # 进行分析...
```

问题:
- 股票已经被选入,只是在分析时跳过
- 浪费了选股过程的资源
- 用户可能困惑:为什么有些股票被选中但不分析?

### 现在的行为 (选股阶段过滤)

```python
# dynamic_stock_selector.py
# 在选股阶段就过滤掉
if enable_price_limits:
    if candidate.price <= 0 or candidate.price < price_min or candidate.price > price_max:
        logger.info(f"过滤: {candidate.name} (价格问题)")
        continue  # 不选入候选列表

# 返回的stocks列表中,所有股票都符合价格要求
# 分析阶段不需要再检查价格
```

优势:
- ✅ 提前过滤,不浪费后续资源
- ✅ 选股结果更精准
- ✅ 逻辑更清晰:选股→过滤→分析
- ✅ 日志更明确,用户能看到过滤原因

## 注意事项

1. **网络依赖**: 价格获取依赖akshare API,网络问题会导致无法获取价格
   - 解决方案: 系统会记录警告,并过滤掉无价格数据的股票

2. **性能考虑**: 批量获取所有A股价格可能较慢(几千只股票)
   - 优化: 只有启用价格限制时才获取
   - 优化: 批量获取比逐个获取快得多
   - 优化: 跳过已有价格数据的股票

3. **缓存**: 目前未实现价格缓存
   - 改进空间: 可以添加5分钟价格缓存,避免短时间内重复获取

4. **实时性**: 价格数据是调用时的快照
   - 场景: 选股时是15元,分析时可能已变化
   - 影响: 可接受,选股本身就是基于某个时间点的快照

## 未来改进方向

1. **价格缓存机制**
   ```python
   # 缓存价格数据5分钟
   cache_key = f"prices_{datetime.now().strftime('%Y%m%d_%H%M')}"
   ```

2. **多数据源容错**
   ```python
   # 如果akshare失败,尝试tushare或yfinance
   if price_from_akshare is None:
       price = try_tushare(symbol) or try_yfinance(symbol)
   ```

3. **价格数据预加载**
   ```python
   # 在系统启动时预加载常用股票价格
   def preload_prices():
       # 加载配置股票的价格
       pass
   ```

## 总结

✅ **功能已完整实现**
✅ **在选股阶段就过滤掉不符合价格限制的股票**
✅ **不会等到分析阶段才跳过**
✅ **提供详细的过滤日志**
✅ **批量获取价格,效率较高**
✅ **容错处理,网络失败时安全过滤**
