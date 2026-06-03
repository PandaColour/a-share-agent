# A股量化交易系统

A 股量化交易系统，结合 AI 因子分析和多数据源，实现智能选股、持仓分析和历史回测。

## 功能介绍

### 运行模式

| 模式 | 命令 | 说明 |
|------|------|------|
| 选股分析 | `python main.py --mode select` | 动态选股 + AI 多维分析，生成推荐列表 |
| 持仓分析 | `python main.py --mode hold` | 分析持仓股票（仅 buy_flag=true），收益追踪 + 风险预警 |
| 全分析 | `python main.py --mode both` | 选股 + 持仓一站式分析 |
| 历史回测 | `python main.py --mode backtest` | 指定日期范围的历史数据回测，含收益/风险指标 |

### AI 因子系统

- 自动因子生成：每次启动自动生成 2-3 个新因子，持续扩展因子库
- 多模板支持：动量、波动率、量价、反转、技术形态等因子模板
- 智能权重优化：基于 IC 分析自动评估和调整因子权重
- 因子自动筛选：自动禁用表现不佳的因子，保持因子池质量

### 智能股票选择

- 多源整合：配置股票 + 潜力股挖掘 + 龙虎榜热点
- 前日涨幅过滤：自动过滤前日涨幅过大的股票，提高买入可行性
- 创业板过滤：可配置排除创业板股票

### 多数据源架构

- **AkShare**：免费 A 股数据源（默认）
- **Tushare**：专业金融数据接口
- **YFinance**：Yahoo Finance 全球数据
- 智能切换：主数据源失败时自动切换到备用源

### 回测系统

- 历史数据回测，支持指定日期范围或向前 N 个月
- 关键指标：总收益率、年化收益率、夏普比率、最大回撤、胜率
- 输出：回测报告（JSON/Markdown）、交易记录、K 线图

### 输出文件

分析结果统一保存在 `outputs/YYYYMMDD_HHMMSS/` 目录下：

- `analysis_summary.csv` — 选股分析汇总表
- `analysis_detailed.json` — 完整分析结果
- `holdings_analysis.csv` — 持仓分析报表（hold/both 模式）
- `backtest_results.json` — 回测结果（backtest 模式）
- `backtest_result.md` — 回测 Markdown 报告

---

## 虚拟环境初始化

项目使用 `.venv` 作为虚拟环境目录。初始化步骤：

### 1. 创建虚拟环境

```bash
# Windows (PowerShell)
python -m venv .venv

# Windows (CMD)
python -m venv .venv
```

### 2. 激活虚拟环境

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat

# Linux / macOS
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

> **注意**：TA-Lib 需要系统级 C 库支持。Windows 下推荐使用预编译包：
> - 下载地址：https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
> - 选择对应 Python 版本的 whl 文件，使用 `pip install <文件名>.whl` 安装
>
> 如果 TA-Lib 安装失败，AI 因子系统会自动降级，不影响基础分析功能。

### 4. 验证安装

```bash
# 验证基础依赖
python -c "import pandas, numpy, yfinance, akshare; print('基础依赖正常')"

# 验证 AI 因子依赖（可选）
python -c "import talib; print('TA-Lib 正常')" || echo "TA-Lib 未安装，AI 因子已禁用"
```

---

## 启动运行

### 配置

项目配置集中在 `config/unified_config.json`。首次使用需要复制示例文件：

```bash
cp config/unified_config.json.example config/unified_config.json
```
添加tushare key 和 大模型key

主要配置项：
- **数据源**：设置主/备用数据源及其 Token（Tushare 需要）
- **AI 模型**：配置 AI 分析所使用的模型端点
- **分析参数**：价格过滤、股票数量限制等

### 运行

```bash
# 确保虚拟环境已激活
# 全分析模式（推荐）
python main.py --mode both

# 选股分析
python main.py --mode select

# 持仓分析
python main.py --mode hold

# 历史回测（最近 3 个月）
python main.py --mode backtest

# 指定日期回测
python main.py --mode backtest --start-date 2025-01-01 --end-date 2025-06-01
```

### 运行流程

系统执行分为两个阶段：

1. **初始化 + 选股**：加载配置 → 初始化 AI 因子系统 → 动态选股
2. **批量分析**：单线程收集股票数据 → 多线程并行 AI 分析 → 输出结果

---

## 免责声明

本系统仅用于研究学习，不构成投资建议。投资有风险，请谨慎决策。

## 感谢支持

![谢谢支持](weixin.jpg)
联系方式: <panda.colour@qq.com>
