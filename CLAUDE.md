# CLAUDE.md

此文件为Claude Code (claude.ai/code)在此代码仓库中工作时提供指导。
## 开发要求
### 核心原则
1. 单一职责原则(SRP):每个函数或类应专注单一功能，避免功能混杂。
2. DRY原则(Don't Repeat Yourself):提取重复代码为独立函数或模块，减少冗余。
3. 开闭原则(OCP):对扩展开放、对修改封闭，避免直接修改已有代码。
4. KISS原则(Keep It Simple, Stupid):保持代码简洁，避免过度复杂化。

### 具体技巧
1.提取公共逻辑: 将重复代码块提炼为独立函数或类，例如计算面积和体积的公共逻辑。
2.简化条件判断: 使用三元运算符或提前返回等方式优化复杂条件语句。
3.优化变量命名: 使用清晰易懂的变量名提升代码自解释性，例如将x改为data。
4.重构函数结构: 确保每个函数仅完成单一职责，便于测试和维护。

### 目标
1. 提高可读性：减少对注释的依赖，使逻辑更直观。
2. 降低维护成本：通过模块化减少修改风险。

## 项目概述

这是一个基于TradingAgents框架的A股量化交易系统。它是一个综合性的Python金融分析系统，结合传统金融分析与AI增强因子，用于股票分析和交易策略生成。

## 系统架构

### 核心模块

**`src/agents/`** - 多智能体协作系统
- `fundamental_analyst.py` - 基本面分析师（PE比率、市值、财务指标）
- `technical_analyst.py` - 技术面分析师（均线、RSI、MACD）含AI因子集成
- `sentiment_analyst.py` - 情感面分析师（价格趋势、市场情绪）
- `advanced_decision_engine.py` - 高级决策引擎
- `portfolio_manager.py` - 投资组合管理
- `risk_manager.py` - 风险管理

**`src/factors/`** - AI因子系统（新功能）
- `auto_factor_generator.py` - 自动生成新交易因子
- `factor_manager.py` - 因子管理和协调
- `technical_ai_factors.py` - 基础AI技术因子（模式识别、成交量分析）
- `auto_factor_selector.py` - 基于IC分析的自动因子选择
- `factor_weight_optimizer.py` - 因子权重优化（7种算法）
- `auto_strategy_generator.py` - 自动策略生成
- `strategy_dynamic_adjuster.py` - 动态策略调整

**`src/data/`** - 多数据源提供者
- `data_provider.py` - 原始数据提供者（向后兼容）
- `multi_source_data_provider.py` - 多数据源提供者（AkShare + Tushare + YFinance）

**`src/utils/`** - 工具模块
- `dynamic_stock_selector.py` - 智能股票选择（配置+龙虎榜+社交媒体）
- `ai_models.py` - AI模型接口
- `data_source_config_manager.py` - 数据源配置管理
- `scheduler.py` - 任务调度
- `stock_validator.py` - 股票代码验证

**`src/backtest/`** - 回测系统
- `advanced_backtest_engine.py` - 高级回测引擎
- `backtest_database.py` - 回测数据库
- `data_collector.py` - 回测数据收集

**`test/`** - 测试目录,所有用于测试的脚本都放这里

### 配置系统

所有配置都集中在 `config/unified_config.json` 中：
- **数据源**: 主要/备用数据源配置
- **AI模型**: 各分析师类型的AI模型分配
- **分析设置**: 价格过滤器、股票选择参数
- **回测设置**: 资金管理、交易成本、策略过滤器

## 开发命令

### 主应用程序
```bash
# 运行AI增强股票分析系统（主要功能）
python main.py

# 系统将自动执行：
# 1. 使用自动生成因子初始化AI因子系统
# 2. 运行动态股票选择（配置+龙虎榜+社交媒体）
# 3. 执行四维分析（基本面+技术面+情感面+AI因子）
# 4. 输出综合分析结果
```

### 测试命令
```bash

### 开发和调试命令
```bash
# 环境设置验证
python -c "import pandas, numpy, yfinance, akshare; print('核心依赖正常')"
python -c "import talib; print('TA-Lib正常')" || echo "TA-Lib缺失 - AI因子已禁用"

# 数据源健康检查
python check_akshare_api.py                # 验证AkShare API连接
python debug_data_structure.py             # 调试数据结构问题
python debug_longhu_bang.py                # 调试龙虎榜数据问题

# 配置验证
python -c "from config.config_manager import get_config; print('配置正常' if get_config() else '配置错误')"

# 日志监控
tail -f logs/trading_system.log             # 监控主系统日志
tail -f logs/ai_factor_system.log           # 监控AI因子日志
tail -f logs/backtest.log                   # 监控回测日志

# 性能监控
python -c "import psutil; print(f'内存: {psutil.virtual_memory().percent}%, CPU: {psutil.cpu_percent()}%')"
```

### 安装和设置
```bash
# 完整安装
pip install -r requirements.txt

# 最小安装（无AI因子）
pip install pandas numpy yfinance requests akshare jieba scipy

# TA-Lib安装（AI因子必需）
# Windows: 从 https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib 下载wheel文件
# Linux/Mac: pip install TA-Lib

# 验证安装
python -c "import src.factors; print('AI因子可用')" || echo "AI因子已禁用"
```

### 代码质量命令
```bash
# 注意：此项目尚未配置lint/typecheck
# 建议添加这些工具：
# pip install flake8 mypy black isort

# 手动代码质量检查
find . -name "*.py" -not -path "./.venv/*" | head -5 | xargs python -m py_compile
grep -r "TODO\|FIXME\|XXX" src/ || echo "未发现待处理任务"
```

## 核心功能

### AI因子系统集成
- **自动生成因子**: 系统每次启动时自动生成2-3个新因子
- **因子模板**: 动量、波动率、量价、反转、技术形态
- **AI增强**: 4种AI增强策略用于因子生成
- **动态扩展**: 因子库从2个基础因子增长到8+个因子

### 多智能体分析
- **四维分析**: 传统3个分析师 + AI因子分析师
- **基于置信度的决策**: 每个分析师提供置信度评分
- **AI模型专业化**: 不同分析师类型分配不同AI模型

### 动态股票选择
- **多源整合**: 配置股票 + 龙虎榜 + 社交媒体趋势
- **智能评分**: 多维度评分算法进行股票排序
- **可配置限制**: 各源类型股票数量可调整

### 多数据源架构
- **主备系统**: 数据源间自动故障转移
- **数据源类型**: AkShare（免费）、Tushare（专业）、YFinance（全球）
- **智能切换**: 故障时自动切换数据源
- **故障转移逻辑**: 主要源 → 备用源1 → 备用源2 → 错误（在`unified_config.json`中配置）
- **数据标准化**: 所有数据源通过`MultiSourceDataProvider`提供统一格式数据
- **源健康监控**: 指数退避的自动重试逻辑

## 代码模式和约定

### 导入结构
```python
# 始终使用相对导入从src模块导入
from src.agents.fundamental_analyst import FundamentalAnalyst
from src.data.multi_source_data_provider import MultiSourceDataProvider
from src.factors import AutoFactorSelector, AutoStrategyGenerator
```

### 错误处理模式
```python
# 标准错误处理与优雅降级
try:
    # AI分析
    ai_result = ai_analyzer.analyze(data)
except Exception as e:
    logger.warning(f"AI分析失败: {e}, 回退到传统分析")
    ai_result = traditional_analyzer.analyze(data)

# 数据源故障转移模式
def get_data_with_fallback(symbol, sources):
    for source in sources:
        try:
            return source.get_data(symbol)
        except Exception as e:
            logger.warning(f"数据源 {source.name} 失败: {e}")
    raise DataSourceError("所有数据源都失败")
```

### 日志记录模式
```python
# 每个模块中的标准日志设置
import logging
logger = logging.getLogger(__name__)

# 日志级别使用
logger.info("系统初始化完成")                    # 系统事件
logger.warning("数据源故障转移已激活")            # 故障转移场景
logger.error("符号XXX分析失败")                  # 需要关注的错误
logger.debug("因子计算: 值=0.75")                # 详细调试信息
```

### 配置访问
```python
from config.config_manager import get_config
config = get_config()

# 带默认值的安全配置访问
ai_enabled = config.get('system_settings', {}).get('ai_models', {}).get('enable_ai_analysis', False)
```

### 因子系统集成
```python
# 初始化AI因子系统
from src.factors import create_auto_strategy, validate_factors

# 检查AI因子是否可用
try:
    from src.factors import FactorManager
    ai_factor_available = True
except ImportError:
    ai_factor_available = False
    logger.warning("AI因子不可用，仅使用传统分析")

# 带错误处理的策略生成
if ai_factor_available:
    strategy = create_auto_strategy(symbols, returns_data, factor_data, "multi_factor")
else:
    strategy = traditional_strategy_generator.create(symbols, returns_data)
```

### 数据源使用模式
```python
# 多数据源提供者使用
from src.data.multi_source_data_provider import MultiSourceDataProvider

provider = MultiSourceDataProvider()
data = provider.get_stock_data(symbol)  # 自动源选择和故障转移

# 手动指定数据源（高级用法）
data = provider.get_stock_data(symbol, preferred_source='tushare')
```

### 测试模式
```python
# 测试用模拟数据生成
def generate_mock_data():
    symbols = ['000001.SZ', '600519.SH']
    dates = pd.date_range(start='2024-01-01', end='2024-09-01', freq='D')
    np.random.seed(42)  # 可重现结果

    # 生成一致的测试数据结构
    return {symbol: create_price_data(dates) for symbol in symbols}

# 带AI因子回退的测试设置
def setup_test_environment():
    try:
        from src.factors import FactorManager
        return True, FactorManager()
    except ImportError:
        return False, None
```

### 性能考虑
```python
# 大数据集的内存管理
import gc
import psutil

def process_large_dataset(data):
    # 分块处理
    chunk_size = 1000
    for chunk in chunked(data, chunk_size):
        process_chunk(chunk)
        gc.collect()  # 强制垃圾回收

        # 内存监控
        if psutil.virtual_memory().percent > 80:
            logger.warning("检测到高内存使用")
```

## 输出文件结构

### 分析结果
- `outputs/analysis_YYYYMMDD_HHMMSS.json` - 完整分析结果
- `outputs/comparison_YYYYMMDD_HHMMSS.json` - 对比报告
- `outputs/changes_YYYYMMDD_HHMMSS.json` - 重要变化摘要

### AI因子策略文件
- `ai_strategies/auto_strategy_YYYYMMDD_HHMMSS.json` - 自动生成的策略
- `ai_strategies/factor_performance_report_YYYYMMDD.json` - 因子表现报告
- `ai_strategies/strategy_signals_YYYYMMDD_HHMMSS.json` - 交易信号

### 回测结果
- `backtest_results/backtest_results_YYYYMMDD_HHMMSS.json` - 详细回测结果
- `backtest_results/backtest_report_YYYYMMDD_HHMMSS.txt` - 文本格式报告

### 日志文件
- `logs/trading_system.log` - 主系统日志
- `logs/ai_factor_system.log` - AI因子系统日志
- `logs/backtest.log` - 回测系统日志

## 测试策略

### 测试分类和依赖

#### 1. 单元测试（模拟数据）
- **目的**: 快速验证核心功能，无外部依赖
- **文件**: `test_auto_factor_system.py`, `test_volume_pattern_debug.py`
- **要求**: 无网络访问，无外部API
- **运行时间**: < 30秒
- **数据**: 使用`np.random.seed(42)`生成可重现的模拟数据

#### 2. 集成测试（真实数据）
- **目的**: 验证系统与真实市场数据的集成
- **文件**: `test_ai_factor_real_data.py`, `test_main_with_ai_factors.py`
- **要求**: 网络访问，已配置数据源
- **运行时间**: 2-5分钟，取决于数据源
- **数据**: 来自已配置提供者的实时市场数据

#### 3. 系统测试（端到端）
- **目的**: 包含所有组件的完整系统验证
- **文件**: `test_backtest_multisource.py`, `test_dynamic_stock_selector.py`
- **要求**: 所有依赖，有效配置
- **运行时间**: 完整回测需5-15分钟
- **数据**: 历史市场数据和实时配置

#### 4. 组件测试（特定模块）
- **目的**: 孤立测试单个组件
- **文件**: `test_ai_factor_integration.py`, `test_price_prediction.py`
- **要求**: 因组件而异
- **运行时间**: 每个组件1-3分钟

### 测试数据管理

#### 模拟数据生成
```python
# 测试中使用的标准模拟数据模式
def generate_test_data():
    np.random.seed(42)  # 始终使用相同种子确保可重现性
    symbols = ['000001.SZ', '600519.SH', '000002.SZ']  # 标准测试股票符号
    dates = pd.date_range(start='2024-01-01', end='2024-09-01', freq='D')

    # 生成具有现实模式的价格数据
    base_price = 10.0
    returns = np.random.normal(0.001, 0.02, len(dates))  # 0.1%均值，2%波动率
    prices = base_price * np.exp(np.cumsum(returns))

    return symbols, dates, prices
```

#### 真实数据测试
```python
# 带回退的安全真实数据测试
def test_with_real_data():
    try:
        provider = MultiSourceDataProvider()
        data = provider.get_stock_data('000001.SZ')
        if data is None or len(data) < 100:
            pytest.skip("真实数据不足，跳过测试")
    except Exception as e:
        pytest.skip(f"真实数据不可用: {e}")
```

### 测试故障调试指南

#### 常见故障模式
1. **"AI因子不可用"**
   - **原因**: 缺少TA-Lib或AI因子依赖
   - **解决**: 安装TA-Lib或禁用AI因子运行
   - **检查**: `python -c "import talib; print('正常')"`

2. **"数据源连接失败"**
   - **原因**: 网络问题或API限制超出
   - **解决**: 检查网络，验证API令牌，尝试不同数据源
   - **检查**: `python check_akshare_api.py`

3. **"模拟数据测试失败"**
   - **原因**: 非确定性测试数据生成
   - **解决**: 确保数据生成前设置`np.random.seed(42)`
   - **检查**: 比较生成数据的形状和基本统计

4. **"配置错误"**
   - **原因**: 配置文件无效或缺失
   - **解决**: 验证`config/unified_config.json`格式
   - **检查**: `python -c "from config.config_manager import get_config; print(get_config())"`

#### 测试环境验证
```bash
# 预测试环境检查
python -c "import sys; print(f'Python: {sys.version}')"
python -c "import pandas, numpy; print('核心依赖正常')"
python -c "from src.data.multi_source_data_provider import MultiSourceDataProvider; print('数据提供者正常')"
python -c "from src.factors import FactorManager; print('AI因子正常')" || echo "AI因子已禁用"
```

### 系统化运行测试

#### 快速验证（30秒）
```bash
python test_auto_factor_system.py  # 核心功能
python -c "from src.factors import validate_factors; print('验证正常')"
```

#### 完整测试套件（5-10分钟）
```bash
# 按复杂度顺序运行所有测试
python test_auto_factor_system.py          # 模拟数据测试优先
python test_ai_factor_integration.py       # 组件集成
python test_ai_factor_real_data.py         # 真实数据验证
python test_main_with_ai_factors.py        # 完整系统集成
python test_backtest_multisource.py        # 回测验证
```

#### 调试特定问题
```bash
# 调试数据问题
python debug_data_structure.py
python debug_longhu_bang.py

# 调试AI因子问题
python test_volume_pattern_debug.py
python test_ai_factor_fix.py

# 调试配置问题
python -c "from config.config_manager import get_config; import json; print(json.dumps(get_config(), indent=2))"
```

## 重要依赖

**核心依赖**: pandas, numpy, yfinance, requests, akshare, tushare
**AI因子依赖**: TA-Lib, scikit-learn, cvxpy, matplotlib, seaborn
**可选依赖**: jieba, scipy

注意：如果缺少TA-Lib或其他AI因子依赖，系统会自动禁用AI因子功能并继续使用传统分析。

## 开发注意事项

- 系统支持开发（AkShare）和生产（Tushare）两种配置
- AI模型配置支持多个端点和模型类型
- 因子系统设计为通过自动生成持续扩展
- 所有分析结果包含置信度评分和贡献度分解
- 回测系统计算真实的交易成本和风险指标

## 安全和生产环境考虑

### 🔒 安全要求

#### API密钥管理
```bash
# 关键：配置文件当前包含暴露的API密钥
# 在提交或共享前，更新 config/unified_config.json：

# 将暴露的令牌替换为占位符：
"tushare": {
  "token": "YOUR_TUSHARE_TOKEN_HERE"  # 永远不要提交真实令牌
}

# 对于AI模型，使用环境变量：
"config": {
  "headers": {
    "Authorization": "Bearer ${API_KEY}"  # 生产环境使用环境变量
  }
}
```

#### 配置安全
```python
# 安全配置加载模式
import os
from pathlib import Path

def load_secure_config():
    config = load_base_config()

    # 用环境变量覆盖
    if 'TUSHARE_TOKEN' in os.environ:
        config['system_settings']['data_sources']['tushare']['token'] = os.environ['TUSHARE_TOKEN']

    if 'AI_API_KEY' in os.environ:
        config['system_settings']['ai_models']['models']['deepseek_v3']['config']['headers']['Authorization'] = f"Bearer {os.environ['AI_API_KEY']}"

    return config
```

### 🚀 生产环境部署

#### 环境配置
```bash
# 生产环境设置
export TUSHARE_TOKEN="your_production_token"
export AI_API_KEY="your_production_ai_key"
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# 设置生产数据源
export PRIMARY_DATA_SOURCE="tushare"
export ENABLE_AI_ANALYSIS="true"
```

#### 资源管理
```python
# 生产环境内存和CPU监控
import psutil
import logging

def monitor_system_resources():
    memory_percent = psutil.virtual_memory().percent
    cpu_percent = psutil.cpu_percent(interval=1)

    if memory_percent > 85:
        logging.warning(f"高内存使用率: {memory_percent}%")
        # 实现内存清理或进程限流

    if cpu_percent > 90:
        logging.warning(f"高CPU使用率: {cpu_percent}%")
        # 实现处理限流
```

### 📊 性能优化

#### 大数据集处理
```python
# 生产数据集优化
def optimize_for_production():
    # 对大数据集使用分块处理
    chunk_size = min(1000, max(100, available_memory_mb // 10))

    # 实现数据缓存
    from functools import lru_cache

    @lru_cache(maxsize=256)
    def cached_data_fetch(symbol, date_range):
        return expensive_data_operation(symbol, date_range)
```

#### 数据库连接
```python
# 生产环境连接池
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

def create_production_engine():
    return create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600
    )
```

### 🛡️ 错误处理和监控

#### 生产日志记录
```python
# 生产日志配置
import logging
from logging.handlers import RotatingFileHandler, SMTPHandler

def setup_production_logging():
    # 轮换文件处理器
    file_handler = RotatingFileHandler(
        'logs/production.log',
        maxBytes=100*1024*1024,  # 100MB
        backupCount=10
    )

    # 关键错误的邮件通知
    if SMTP_ENABLED:
        mail_handler = SMTPHandler(
            mailhost=SMTP_SERVER,
            fromaddr=FROM_EMAIL,
            toaddrs=ADMIN_EMAILS,
            subject='交易系统关键错误'
        )
        mail_handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(mail_handler)
```

#### 健康检查
```python
# 系统健康监控
def health_check():
    checks = {
        'data_sources': check_data_source_connectivity(),
        'ai_models': check_ai_model_availability(),
        'disk_space': check_disk_space(),
        'memory': check_memory_usage(),
        'factor_system': check_factor_system_status()
    }

    failed_checks = [k for k, v in checks.items() if not v]
    if failed_checks:
        logging.error(f"健康检查失败: {failed_checks}")
        return False
    return True
```

### 🔄 文件管理

#### 输出目录管理
```bash
# 生产文件清理策略
# 添加到crontab进行自动清理：

# 保留分析结果30天
find outputs/ -name "*.json" -mtime +30 -delete

# 保留回测结果90天
find backtest_results/ -name "*.json" -mtime +90 -delete

# 压缩旧日志
find logs/ -name "*.log" -mtime +7 -exec gzip {} \;

# 保留压缩日志365天
find logs/ -name "*.log.gz" -mtime +365 -delete
```

#### 备份策略
```python
# 关键数据自动备份
import shutil
from datetime import datetime

def backup_critical_data():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f"backups/backup_{timestamp}"

    # 备份配置
    shutil.copytree('config/', f"{backup_dir}/config/")

    # 备份最近的分析结果
    shutil.copytree('outputs/', f"{backup_dir}/outputs/")

    # 备份AI策略
    if os.path.exists('ai_strategies/'):
        shutil.copytree('ai_strategies/', f"{backup_dir}/ai_strategies/")
```

### ⚠️ 重要生产警告

1. **API速率限制**: 监控API使用量避免触及速率限制
2. **数据质量**: 对所有外部数据源实施数据验证
3. **模型性能**: 定期验证AI模型性能，如降级则更新
4. **因子漂移**: 监控因子性能，必要时重新训练
5. **内存泄漏**: 监控长期运行进程的内存泄漏
6. **磁盘空间**: 监控磁盘使用，特别是logs/和outputs/目录
7. **网络依赖**: 对所有网络调用实施适当的超时和重试逻辑

### 🔧 维护命令

```bash
# 日常维护
python -c "from maintenance import daily_health_check; daily_health_check()"

# 周期清理
find outputs/ -name "*.json" -mtime +7 | head -100 | xargs rm -f

# 月度因子重训练（如已实现）
python scripts/retrain_factors.py --mode=production

# 季度完整系统验证
python test_main_with_ai_factors.py --production-mode
```