# 统一输出目录实现

## 改造目标

实现持仓分析和选股分析结果的统一输出：
- `--mode both` 时，两类分析结果输出到同一个目录
- `--mode hold` 时，单独创建时间戳目录
- `--mode select` 时，使用统一的时间戳目录
- 在系统启动时确定输出目录，避免参数传递

## 输出目录结构

### 1. hold 模式（仅持仓分析）
```
outputs/
  └── holdings_20250105_143022/
      └── holdings_analysis.csv
```

### 2. select 模式（仅选股分析）
```
outputs/
  └── 20250105_143022/
      ├── analysis_summary.csv
      ├── analysis_detailed.json
      ├── analyst_details.json
      └── README.md
```

### 3. both 模式（统一输出）
```
outputs/
  └── 20250105_143022/
      ├── holdings_analysis.csv        # 持仓分析结果
      ├── analysis_summary.csv         # 选股分析结果
      ├── analysis_detailed.json
      ├── analyst_details.json
      └── README.md
```

## 实现要点

### 1. main.py 中的输出目录确定（启动时）

```python
# 确定输出目录（在系统启动时就确定，避免后续传递）
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
if args.mode == 'hold':
    # hold 模式：单独的时间戳目录
    output_dir = os.path.join("outputs", f"holdings_{timestamp}")
else:
    # select 和 both 模式：使用统一的时间戳目录
    output_dir = os.path.join("outputs", timestamp)

os.makedirs(output_dir, exist_ok=True)
```

### 2. 系统初始化时设置输出目录

```python
system = AShareTradingAgentsSystem()
# 设置输出目录（统一输出路径）
system.output_manager.output_dir = output_dir
```

### 3. 持仓分析流程传递输出目录

```python
def execute_hold_stock_analysis(system, config, main_logger, start_time, output_dir):
    """执行持仓股票分析，返回分析结果供复用"""
    hold_process = HoldStockProcess(system, config, output_dir=output_dir)
    result = hold_process.execute_full_process()
    # ...
```

### 4. HoldStockProcess 使用输出目录

```python
class HoldStockProcess:
    def __init__(self, system=None, config=None, output_dir=None):
        self.output_dir = output_dir  # 保存输出目录

    def save_analysis_to_csv(self, position_analyses: List[Dict]):
        # 确定输出目录
        if self.output_dir:
            output_path = Path(self.output_dir)
        else:
            # 回退到默认行为
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = Path("outputs") / timestamp

        # 文件名不再包含时间戳（已在目录名中）
        csv_filename = output_path / "holdings_analysis.csv"
```

### 5. AnalysisOutputManager 使用预设目录

```python
class AnalysisOutputManager:
    def __init__(self):
        self.output_dir = None  # 输出目录，可在系统初始化后设置

    def save_results(self, results: List[Dict], output_dir: str = "outputs"):
        # 确定输出目录
        if self.output_dir:
            # 使用预设的输出目录（both/select模式下由main.py设置）
            session_dir = Path(self.output_dir)
        else:
            # 创建时间戳文件夹（向后兼容）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_output_dir = Path(output_dir)
            base_output_dir.mkdir(exist_ok=True)
            session_dir = base_output_dir / timestamp

        session_dir.mkdir(parents=True, exist_ok=True)
```

## 涉及的文件修改

### 1. `main.py`
- **Line 1274-1284**: 添加输出目录确定逻辑
- **Line 1321**: 设置 `system.output_manager.output_dir`
- **Line 1201**: `execute_hold_stock_analysis()` 添加 `output_dir` 参数
- **Line 1388, 1395**: 调用时传递 `output_dir`

### 2. `src/process/hold_stock_process.py`
- **Line 23**: `__init__()` 添加 `output_dir` 参数
- **Line 34**: 保存 `self.output_dir`
- **Line 305-358**: `save_analysis_to_csv()` 使用 `self.output_dir`
- **Line 327**: 简化文件名为 `holdings_analysis.csv`

### 3. `src/output/analysis_output_manager.py`
- **Line 25**: 添加 `self.output_dir` 属性
- **Line 373-384**: `save_results()` 使用 `self.output_dir` 优先

## 优势

1. **统一管理**: both 模式下所有分析结果在同一目录，便于查看和对比
2. **避免参数传递**: 输出目录在启动时确定并设置，不需要层层传递
3. **向后兼容**: 如果 `output_dir` 未设置，自动回退到创建时间戳目录
4. **清晰结构**: 单独的 hold 模式使用 `holdings_` 前缀，易于区分

## 测试验证

```bash
# 测试 hold 模式
python main.py --mode hold
# 预期: outputs/holdings_YYYYMMDD_HHMMSS/holdings_analysis.csv

# 测试 select 模式
python main.py --mode select
# 预期: outputs/YYYYMMDD_HHMMSS/analysis_summary.csv

# 测试 both 模式
python main.py --mode both
# 预期: outputs/YYYYMMDD_HHMMSS/
#        ├── holdings_analysis.csv
#        └── analysis_summary.csv
```

## 相关文档

- [持股分析系统](./hold_stock_analysis_system.md)
- [配置清理](./config_cleanup.md)
