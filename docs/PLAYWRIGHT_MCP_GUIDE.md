# Playwright MCP 使用指南

## 简介

Playwright MCP (Model Context Protocol) 为 AI 应用提供浏览器自动化能力，可用于抓取财经新闻、监控龙虎榜、获取社交媒体数据等。

## 安装

```bash
npm install -g @playwright/mcp
```

## 配置场景

### 1. 财经新闻抓取（推荐用于情感分析增强）

**用途**: 抓取东方财富、同花顺、新浪财经等网站的股票新闻

**启动方式**:
```bash
# Windows
scripts\start-playwright-news.bat

# Linux/Mac
npx @playwright/mcp --browser chrome --headless --port 3001
```

**目标网站**:
- 东方财富: https://quote.eastmoney.com/{股票代码}.html
- 同花顺: http://stockpage.10jqka.com.cn/{股票代码}/
- 新浪财经: https://finance.sina.com.cn/realstock/company/{股票代码}/nc.shtml

**输出目录**: `./playwright-output/news/`

---

### 2. 龙虎榜监控（推荐用于动态选股）

**用途**: 实时监控龙虎榜数据，替代或增强现有的 AkShare 龙虎榜数据

**启动方式**:
```bash
# Windows
scripts\start-playwright-longhu.bat

# Linux/Mac
npx @playwright/mcp --browser chrome --headless --save-trace --port 3003
```

**目标网站**:
- 东方财富龙虎榜: http://data.eastmoney.com/stock/tradedetail.html

**输出目录**: `./playwright-output/longhu/`

---

### 3. 调试模式（开发使用）

**用途**: 可视化浏览器，用于开发和调试爬虫脚本

**启动方式**:
```bash
# Windows
scripts\start-playwright-debug.bat

# Linux/Mac
npx @playwright/mcp --browser chrome --save-video 1280x720 --port 3002
```

**特点**:
- 显示浏览器窗口
- 保存操作录像
- 保存 Trace 文件用于回放

**输出目录**: `./playwright-output/debug/`

---

## Python 集成示例

见 `examples/playwright_news_scraper.py`

**基本流程**:
1. 启动 Playwright MCP 服务（后台运行）
2. Python 程序通过 HTTP/WebSocket 连接 MCP 服务
3. 发送浏览器自动化指令
4. 接收抓取的数据

**集成点建议**:

### A. 增强情感分析师
在 `src/agents/sentiment_analyst.py` 中集成：
```python
# 原有逻辑：从 AkShare 获取新闻
news_data = self.data_provider.get_stock_news(symbol)

# 新增：从 Playwright MCP 获取更丰富的新闻
if playwright_mcp_enabled:
    web_news = await scrape_eastmoney_news(symbol)
    news_data.extend(web_news)
```

### B. 增强龙虎榜选股
在 `src/utils/dynamic_stock_selector.py` 中集成：
```python
# 原有逻辑：从 AkShare 获取龙虎榜
longhu_stocks = ak.stock_lhb_detail_daily_sina()

# 新增：从网页实时抓取
if playwright_mcp_enabled:
    web_longhu = await scrape_longhu_realtime()
    # 合并去重
```

### C. 社交媒体情绪监控
创建新的数据源：
```python
# src/data/social_media_provider.py
class SocialMediaProvider:
    async def get_xueqiu_sentiment(self, symbol):
        """获取雪球讨论情绪"""
        # 使用 Playwright MCP 抓取
```

---

## 常用命令

### 基础启动
```bash
npx @playwright/mcp
```

### 指定浏览器和端口
```bash
npx @playwright/mcp --browser chrome --port 3001
```

### 无头模式（生产环境）
```bash
npx @playwright/mcp --headless
```

### 保存会话和追踪
```bash
npx @playwright/mcp --save-session --save-trace --output-dir ./output
```

### 使用代理
```bash
npx @playwright/mcp --proxy-server http://proxy.example.com:8080
```

### 模拟移动设备
```bash
npx @playwright/mcp --device "iPhone 15"
```

---

## 与现有系统集成建议

### 短期（快速集成）
1. 手动运行 Playwright MCP 服务
2. 使用简单的 HTTP 请求或命令行脚本抓取数据
3. 将抓取的数据保存为 JSON，供现有分析师读取

### 中期（深度集成）
1. 在 `config/unified_config.json` 中添加 Playwright MCP 配置
2. 创建 `src/data/web_scraper.py` 封装 MCP 客户端
3. 在各分析师中可选启用网页数据增强

### 长期（全面优化）
1. 实现数据缓存机制，避免频繁抓取
2. 添加反爬虫策略（随机延迟、User-Agent 轮换）
3. 实现分布式抓取，提高效率
4. 监控数据质量，自动降级到备用数据源

---

## 注意事项

### 法律合规
- 遵守网站 robots.txt 规则
- 控制请求频率，避免对服务器造成压力
- 仅用于个人研究和学习，不用于商业用途

### 技术限制
- 某些网站有反爬虫机制，可能需要额外处理
- 建议设置合理的超时时间
- 注意内存占用，长时间运行可能需要重启

### 数据质量
- 网页结构可能变化，需要定期维护选择器
- 建议设置数据验证逻辑
- 与 API 数据对比验证

---

## 故障排查

### 端口被占用
```bash
# 查找占用端口的进程
netstat -ano | findstr :3001

# 杀死进程或使用不同端口
npx @playwright/mcp --port 3010
```

### 浏览器启动失败
```bash
# 手动安装 Playwright 浏览器
npx playwright install chrome
```

### 连接超时
- 检查网络连接
- 增加超时时间: `--timeout-navigation 120000`
- 检查目标网站是否可访问

---

## 相关资源

- Playwright MCP GitHub: https://github.com/microsoft/playwright-mcp
- Playwright 文档: https://playwright.dev/
- MCP 协议: https://modelcontextprotocol.io/

---

## 下一步

1. ✅ Playwright MCP 已安装
2. ⏳ 运行测试脚本验证功能
3. ⏳ 选择集成点（建议先从情感分析增强开始）
4. ⏳ 实现 MCP 客户端封装
5. ⏳ 集成到现有分析流程