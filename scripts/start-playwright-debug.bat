@echo off
REM 启动调试模式（可视化浏览器）
echo 正在启动 Playwright MCP - 调试模式（可视化）...

npx @playwright/mcp ^
  --browser chrome ^
  --viewport-size 1600x900 ^
  --timeout-navigation 120000 ^
  --timeout-action 30000 ^
  --output-dir ./playwright-output/debug ^
  --save-session ^
  --save-trace ^
  --save-video 1280x720 ^
  --user-data-dir ./playwright-data/debug-profile ^
  --port 3002

pause