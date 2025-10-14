@echo off
REM 启动财经新闻抓取器
echo 正在启动 Playwright MCP - 财经新闻抓取模式...

npx @playwright/mcp ^
  --browser chrome ^
  --headless ^
  --viewport-size 1920x1080 ^
  --timeout-navigation 30000 ^
  --timeout-action 10000 ^
  --output-dir ./playwright-output/news ^
  --save-session ^
  --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" ^
  --port 3001

pause