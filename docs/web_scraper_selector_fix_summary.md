# 网页抓取选择器修复总结

## 📅 修复日期
2025年11月7日

## 🎯 问题背景

### 用户反馈
> "网页都可以打开，是不是选择器有问题？不然怎么会超时"

用户正确识别了核心问题：**不是网络问题，而是CSS选择器失效**。

### 错误日志
```
2025-11-07 14:01:58 - ⚠️ 新闻列表加载超时: 002196.SZ
2025-11-07 14:02:34 - ⚠️ 雪球讨论区加载超时: 002196.SZ
```

### 根本原因
财经网站（东方财富、雪球）经常改版，导致旧的CSS选择器失效：
- **东方财富**: 从 `.news-list` 改为 Vue容器结构
- **雪球**: 从 `.timeline` 改为卡片布局

---

## ✅ 实施的解决方案

### 1. 多选择器重试机制（核心修复）

#### 设计思路
```
尝试选择器1（3秒超时） → 失败
↓
尝试选择器2（3秒超时） → 失败
↓
尝试选择器3（3秒超时） → 成功 ✅
↓
使用该选择器提取数据
```

#### 东方财富新闻抓取
**文件**: `src/data/web_scraper.py` (line 79-237)

**选择器优先级**:
```python
[
    # 第一优先级：现代网页框架
    "#app",                          # Vue应用容器
    "[class*='quote-']",             # 行情相关类名

    # 第二优先级：语义化选择器
    "div[class*='news']",            # 包含news的div
    "ul[class*='news']",             # 包含news的列表
    "article",                       # HTML5文章标签

    # 第三优先级：特定网站模式
    "a[href*='finance.eastmoney']", # 东方财富新闻链接

    # 第四优先级：旧版选择器（兼容）
    ".news-list",
    ".newslist",
    "#newslist"
]
```

**降级方案**:
如果所有选择器都失败，尝试抓取任何包含 `news` 或 `finance` 的链接：
```python
all_links = await page.query_selector_all("a[href*='news'], a[href*='finance']")
# 过滤标题长度 > 5 的有效新闻
```

#### 雪球讨论抓取
**文件**: `src/data/web_scraper.py` (line 239-425)

**选择器优先级**:
```python
[
    # 第一优先级：现代网页框架
    "#app",                          # Vue应用容器
    "article",                       # HTML5文章标签

    # 第二优先级：布局模式
    "[class*='card']",               # 卡片布局
    "[class*='post']",               # 帖子容器
    "div[class*='timeline']",        # 时间线容器
    "div[class*='feed']",            # 信息流容器

    # 第三优先级：特定网站模式
    "a[href*='/status/']",           # 雪球帖子链接格式
    "div[class*='content']",         # 内容容器

    # 第四优先级：旧版选择器（兼容）
    ".timeline",
    ".feed-list",
    ".timeline__item",
    ".feed-item"
]
```

**降级方案**:
```python
all_items = await page.query_selector_all("div[class*='item'], article, [class*='card']")
# 过滤内容长度 > 10 的有效讨论
```

---

## 📊 关键改进对比

| 维度 | 修复前 | 修复后 |
|-----|-------|-------|
| **选择器数量** | 2-3个 | 10+个 |
| **超时时间** | 5-10秒 | 3秒（快速失败） |
| **重试机制** | ❌ 无 | ✅ 逐个重试 |
| **降级策略** | ❌ 无 | ✅ 通用选择器兜底 |
| **调试信息** | 仅报错 | 显示成功的选择器 |
| **适应性** | 网站改版即失效 | 高度适应网页结构变化 |

---

## 🔍 技术细节

### 重试逻辑实现
```python
news_container_found = False
for selector in news_selectors:
    try:
        await page.wait_for_selector(selector, timeout=3000)
        logger.debug(f"  ✓ 找到容器: {selector}")
        news_container_found = True
        break  # 第一个成功即停止
    except PlaywrightTimeoutError:
        continue  # 继续尝试下一个

if not news_container_found:
    # 启动降级方案
    logger.warning(f"⚠️ 无法找到新闻容器: {symbol}")
    logger.info(f"💡 网页可能已改版，建议运行诊断工具")
    # ... 降级逻辑
```

### 超时优化
- **修复前**: 每个选择器组合等待 5-10 秒
- **修复后**: 每个选择器独立等待 3 秒
- **效果**:
  - 如果第一个选择器成功：3秒完成
  - 如果需要尝试10个选择器：最多30秒（但大概率在前3-5个成功）
  - 如果所有选择器失败：启动降级方案，额外3-5秒

### 降级方案设计原则
1. **宁可抓取质量低的数据，也不完全失败**
2. **用户反馈**: 即使降级方案数据不完美，也比空数据有用
3. **数据验证**: 降级方案包含基本过滤（标题长度、内容长度）

---

## 🧪 测试和验证

### 推荐测试流程

#### 1. 诊断工具测试
```bash
python diagnose_web_selectors.py

# 选择要诊断的网站
# 1. 东方财富
# 2. 雪球
# 3. 两者都诊断

# 工具会：
# - 打开浏览器显示页面
# - 尝试所有选择器
# - 保存截图
# - 显示HTML结构
# - 列出有效的选择器
```

#### 2. 实际抓取测试
```bash
# 测试单个股票
python -c "
import asyncio
from src.data.web_scraper import scrape_news_for_sentiment
result = asyncio.run(scrape_news_for_sentiment('002196.SZ'))
print(f'新闻: {len(result[\"news\"])} 条')
print(f'讨论: {len(result[\"discussions\"])} 条')
"

# 测试完整分析流程
python main.py --mode select
```

#### 3. 性能测试
```python
# 监控超时时间
import time

start = time.time()
result = asyncio.run(scraper.scrape_eastmoney_news('600519'))
elapsed = time.time() - start

print(f"耗时: {elapsed:.2f}秒")
print(f"结果数: {len(result)}")
```

### 预期结果

#### 成功场景
```
📰 抓取东方财富新闻: https://quote.eastmoney.com/002196.html
  ✓ 找到容器: #app
  ✓ 使用项目选择器: a[href*='finance.eastmoney'] (找到 25 项)
✅ 抓取到 10 条东方财富新闻
```

#### 降级场景
```
📰 抓取东方财富新闻: https://quote.eastmoney.com/002196.html
⚠️ 无法找到新闻容器: 002196.SZ
💡 网页可能已改版，建议运行诊断工具
  降级方案: 找到 15 个可能的新闻链接
✅ 降级方案抓取到 8 条新闻
```

#### 完全失败场景（极少）
```
📰 抓取东方财富新闻: https://quote.eastmoney.com/002196.html
⚠️ 无法找到新闻容器: 002196.SZ
💡 网页可能已改版，建议运行诊断工具
  降级方案: 找到 0 个可能的新闻链接
❌ 未能抓取到新闻
```

---

## 📝 配置管理

### 重新启用网页抓取
**文件**: `config/unified_config.json` (line 195)

```json
"web_scraping": {
  "enabled": true,  // 改回 true
  "description": "网页数据抓取配置（Playwright增强）- 多选择器重试已修复",
  "eastmoney_news": true,
  "xueqiu_discussions": true,
  "max_news_per_stock": 10,
  "max_discussions_per_stock": 15,
  "timeout_seconds": 30,
  "headless": true
}
```

### 监控和日志
系统会输出详细的调试日志：
```python
logger.debug(f"  ✓ 找到容器: {selector}")           # 成功的选择器
logger.info(f"  降级方案: 找到 {len(items)} 个项")  # 降级方案状态
logger.info(f"✅ 抓取到 {len(results)} 条数据")     # 最终结果
```

---

## 🎉 修复效果

### 鲁棒性提升
- **网站小改版**: 自动切换到可用的选择器，无需人工干预
- **网站大改版**: 降级方案仍能提取基本数据
- **完全不可用**: 明确提示用户运行诊断工具

### 用户体验改善
- **更快的失败**: 3秒超时 vs 10秒超时
- **更多的成功**: 10+个选择器 vs 2-3个选择器
- **更好的反馈**: 显示哪个选择器成功或降级方案状态

### 维护成本降低
- **自适应**: 网站小改版时自动适配
- **易诊断**: 诊断工具快速定位问题
- **易修复**: 只需在选择器数组中添加新模式

---

## 🔄 后续维护建议

### 定期检查（每季度）
```bash
# 1. 运行诊断工具
python diagnose_web_selectors.py

# 2. 检查日志中的降级方案使用率
grep "降级方案" logs/trading_system.log

# 3. 如果降级方案频繁触发，运行诊断工具找到新选择器
```

### 添加新选择器
如果诊断工具找到新的有效选择器，添加到优先级列表：

**文件**: `src/data/web_scraper.py`
```python
news_selectors = [
    "#new-selector-found",  # 添加在这里
    "#app",
    "[class*='quote-']",
    # ... 现有选择器
]
```

### 监控降级率
```bash
# 计算降级方案使用率
grep "降级方案抓取到" logs/trading_system.log | wc -l
# 如果 > 20%，建议更新选择器
```

---

## 📚 相关文档

- `docs/web_scraper_fix_guide.md` - 完整修复指南（含手动修复方法）
- `diagnose_web_selectors.py` - 诊断工具脚本
- `src/data/web_scraper.py` - 网页抓取器源代码

---

## 🙏 致谢

感谢用户准确识别问题根源：
> "网页都可以打开，是不是选择器有问题？不然怎么会超时"

这个洞察直接指导了修复方案的设计。

---

*修复完成时间: 2025-11-07*
*文档版本: 1.0*
