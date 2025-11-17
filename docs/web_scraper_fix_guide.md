# 网页抓取选择器修复指南

## 🐛 问题描述

网页抓取功能超时，虽然网页可以打开，但是选择器无法定位到元素。

**错误日志**:
```
⚠️ 新闻列表加载超时: 002196.SZ
⚠️ 雪球讨论区加载超时: 002196.SZ
```

## 🔍 原因分析

财经网站经常更新页面结构，导致之前的 CSS 选择器失效：

| 网站 | 旧选择器 | 可能失效原因 |
|------|---------|------------|
| 东方财富 | `.news-list, .newslist` | 网站改版，类名变更 |
| 雪球 | `.timeline, .feed-list` | 网站改版，结构调整 |

## ✅ 已完成的修复 (2025-11-07)

### 1. 实现多选择器重试机制 ⭐ **核心修复**
**文件**: `src/data/web_scraper.py`

#### 东方财富新闻抓取 (`scrape_eastmoney_news` - line 79-237)

**修复策略**:
```python
# 1. 尝试多个现代选择器（每个3秒超时）
news_selectors = [
    "#app",                                    # Vue应用容器
    "[class*='quote-']",                       # 行情相关类名
    "div[class*='news']",                      # 包含news的div
    "ul[class*='news']",                       # 包含news的列表
    "article",                                 # HTML5文章标签
    "a[href*='finance.eastmoney']",           # 东方财富新闻链接
    # ... 旧版选择器作为后备
]

# 2. 逐个尝试，第一个成功即停止
for selector in news_selectors:
    try:
        await page.wait_for_selector(selector, timeout=3000)
        news_container_found = True
        break
    except PlaywrightTimeoutError:
        continue

# 3. 降级方案：如果所有选择器都失败
if not news_container_found:
    # 尝试抓取任何包含"news"或"finance"的链接
    all_links = await page.query_selector_all("a[href*='news'], a[href*='finance']")
    # 过滤提取有效新闻（标题长度>5）
```

#### 雪球讨论抓取 (`scrape_xueqiu_discussions` - line 239-425)

**修复策略**:
```python
# 1. 尝试多个现代选择器
discussion_selectors = [
    "#app",                                    # Vue应用容器
    "article",                                 # HTML5文章标签
    "[class*='card']",                        # 卡片布局
    "[class*='post']",                        # 帖子容器
    "div[class*='timeline']",                 # 时间线容器
    "div[class*='feed']",                     # 信息流容器
    "a[href*='/status/']",                    # 雪球帖子链接格式
    # ... 旧版选择器作为后备
]

# 2. 逐个尝试，第一个成功即停止
for selector in discussion_selectors:
    try:
        await page.wait_for_selector(selector, timeout=3000)
        discussion_container_found = True
        break
    except PlaywrightTimeoutError:
        continue

# 3. 降级方案：如果所有选择器都失败
if not discussion_container_found:
    # 尝试抓取任何item、article或card元素
    all_items = await page.query_selector_all("div[class*='item'], article, [class*='card']")
    # 过滤提取有效讨论（内容长度>10）
```

**关键改进**:
- ✅ 超时时间从5秒减少到3秒（快速失败）
- ✅ 支持10+个不同的选择器模式
- ✅ 优先尝试现代网页结构（Vue容器、HTML5标签）
- ✅ 兼容旧版网页结构
- ✅ 降级方案：即使结构化选择器失败，仍能提取基本内容
- ✅ 详细的调试日志（显示哪个选择器成功）

### 2. 降级策略增强

**效果**: 即使网页完全改版，系统也能：
- 东方财富：提取任何包含新闻链接的元素
- 雪球：提取任何包含文本内容的卡片/项目

**输出示例**（降级模式）:
```
💡 网页可能已改版，建议运行诊断工具
  降级方案: 找到 15 个可能的新闻链接
✅ 降级方案抓取到 10 条新闻
```

### 3. 增加诊断工具

**文件**: `diagnose_web_selectors.py` (已创建)

超时时会提示用户运行诊断工具：
```
💡 提示: 网页选择器可能已失效，请运行 'python diagnose_web_selectors.py' 检查
```

## 🔧 如何修复选择器（完整步骤）

### 方法1: 使用诊断工具（推荐）

1. **运行诊断工具**:
```bash
python diagnose_web_selectors.py
```

2. **选择要诊断的网站**:
```
1. 东方财富
2. 雪球
3. 两者都诊断
```

3. **检查输出**:
工具会：
- 打开浏览器并访问页面
- 尝试所有可能的选择器
- 保存页面截图
- 显示HTML结构样本
- 列出找到的有效选择器

4. **更新代码**:
根据诊断结果，更新 `src/data/web_scraper.py` 中的选择器。

### 方法2: 手动检查（浏览器开发者工具）

#### 东方财富新闻

1. 访问: `https://quote.eastmoney.com/002196.html`
2. 按 `F12` 打开开发者工具
3. 定位新闻列表元素
4. 右键 → 复制 → Copy selector
5. 更新 `web_scraper.py` line 110-113

**可能的新选择器**:
- `[class*="news"]` - 包含 "news" 的类名
- `#newsContainer` - 新闻容器ID
- `.stock-news` - 股票新闻区域
- `div[data-type="news"]` - data 属性选择器

#### 雪球讨论

1. 访问: `https://xueqiu.com/S/SZ002196`
2. 按 `F12` 打开开发者工具
3. 定位讨论列表元素
4. 右键 → 复制 → Copy selector
5. 更新 `web_scraper.py` line 208-211

**可能的新选择器**:
- `article` - 文章标签
- `[class*="card"]` - 卡片容器
- `.post-list` - 帖子列表
- `div[data-type="post"]` - data 属性选择器

### 方法3: 使用更通用的选择器

如果网站结构经常变化，可以使用更通用的选择器：

```python
# 东方财富 - 通用选择器
selectors = [
    "[class*='news']",      # 任何包含 news 的类名
    "[id*='news']",         # 任何包含 news 的ID
    "a[href*='news']",      # 新闻链接
    "div:has(> a[title])",  # 包含标题链接的div
]

# 雪球 - 通用选择器
selectors = [
    "article",              # HTML5 文章标签
    "[class*='card']",      # 卡片布局
    "[class*='item']",      # 列表项
    "div:has(> .title)",    # 包含标题的div
]
```

## 📝 代码更新示例

### 更新东方财富选择器

**文件**: `src/data/web_scraper.py` (line 107-118)

```python
# 等待新闻区域加载
try:
    # 方案A: 尝试多个选择器（逐个尝试，第一个成功即可）
    selectors = [
        "#newslist",              # 新的ID选择器
        ".news-container",        # 新的类名选择器
        "[data-type='news']",     # data属性选择器
        "[class*='news']"         # 通配类名选择器
    ]

    loaded = False
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=5000)
            logger.info(f"✓ 使用选择器: {selector}")
            loaded = True
            break
        except PlaywrightTimeoutError:
            continue

    if not loaded:
        raise PlaywrightTimeoutError("所有选择器均失败")

except PlaywrightTimeoutError:
    logger.warning(f"⚠️ 新闻列表加载超时: {symbol}")
    await page.close()
    return []
```

### 更新雪球选择器

**文件**: `src/data/web_scraper.py` (line 205-216)

```python
# 等待讨论区加载
try:
    # 尝试多个选择器
    selectors = [
        "article",                # HTML5 article标签
        "[class*='card']",        # 卡片布局
        "[class*='post']",        # 帖子容器
        ".discussion-list"        # 讨论列表
    ]

    loaded = False
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=5000)
            logger.info(f"✓ 使用选择器: {selector}")
            loaded = True
            break
        except PlaywrightTimeoutError:
            continue

    if not loaded:
        raise PlaywrightTimeoutError("所有选择器均失败")

except PlaywrightTimeoutError:
    logger.warning(f"⚠️ 雪球讨论区加载超时: {symbol}")
    await page.close()
    return []
```

## 🎯 重新启用网页抓取

修复选择器后，重新启用功能：

**文件**: `config/unified_config.json` (line 195)

```json
"web_scraping": {
  "enabled": true,  // 改回 true
  "description": "网页数据抓取配置（Playwright增强）- 已修复选择器"
}
```

## 🧪 测试修复

```bash
# 1. 运行诊断工具验证
python diagnose_web_selectors.py

# 2. 单独测试网页抓取
python -c "
import asyncio
from src.data.web_scraper import scrape_news_for_sentiment
result = asyncio.run(scrape_news_for_sentiment('002196.SZ'))
print(f'新闻: {len(result[\"news\"])} 条')
print(f'讨论: {len(result[\"discussions\"])} 条')
"

# 3. 运行完整分析测试
python main.py --mode select
```

## 💡 最佳实践

### 1. 定期更新选择器
网站可能每3-6个月改版一次，建议：
- 每季度运行诊断工具检查
- 关注日志中的超时警告
- 建立选择器版本管理

### 2. 使用降级策略
```python
# 即使网页抓取失败，系统仍然可以使用传统新闻源
if len(news) == 0:
    logger.info("网页抓取失败，使用传统新闻API")
    news = traditional_news_api.fetch(symbol)
```

### 3. 设置合理的超时
```json
"web_scraping": {
  "timeout_seconds": 30,      // 页面加载总超时
  "selector_timeout": 5,      // 选择器等待超时（新增）
  "retry_count": 2            // 重试次数（新增）
}
```

## 📚 相关资源

- Playwright 文档: https://playwright.dev/python/
- CSS 选择器参考: https://developer.mozilla.org/zh-CN/docs/Web/CSS/CSS_Selectors
- 东方财富官网: https://quote.eastmoney.com/
- 雪球官网: https://xueqiu.com/

## 🔄 版本历史

- **2025-11-07**: 临时禁用网页抓取，减少超时时间，创建诊断工具
- **待更新**: 修复选择器后重新启用

---

*最后更新: 2025-11-07*
