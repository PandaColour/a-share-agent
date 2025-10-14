@echo off
REM 启动龙虎榜监控器
echo 正在启动 Playwright MCP - 龙虎榜监控模式...

npx @playwright/mcp ^
  --browser chrome ^
  --headless ^
  --viewport-size 1920x1080 ^
  --timeout-navigation 60000 ^
  --timeout-action 15000 ^
  --output-dir ./playwright-output/longhu ^
  --save-session ^
  --save-trace ^
  --ignore-https-errors ^
  --port 3003

pause