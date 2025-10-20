# -*- coding: utf-8 -*-
"""
简化回测系统入口
基于outputs目录中的历史分析结果进行回测，无需重新获取股票数据
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.backtest.simple_backtest_engine import SimpleBacktestEngine


def setup_logging():
    """设置日志"""
    # 确保logs目录存在
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 使用与系统一致的日志文件名
    log_file = log_dir / "backtest_simple.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )


def main():
    """主函数"""
    print("="*80)
    print("简化回测系统 - 基于历史分析结果")
    print("="*80)
    print()

    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # 创建回测引擎
        engine = SimpleBacktestEngine(outputs_dir="outputs")

        # 运行回测
        # min_continuous_days=2: 至少需要2天的连续分析数据
        result = engine.run_backtest(min_continuous_days=2)

        # 检查是否有错误
        if "error" in result:
            logger.error(f"❌ 回测失败: {result['error']}")
            return 1

        # 保存结果
        output_path = engine.save_results(result)

        print()
        print("="*80)
        print("回测完成！")
        print("="*80)
        print()
        print("快速统计:")
        overall = result.get("overall_stats", {})
        print(f"  总交易次数: {overall.get('total_trades', 0)}")
        print(f"  平均收益率: {overall.get('avg_return', 0):.2%}")
        print(f"  胜率: {overall.get('win_rate', 0):.2%}")
        print()
        print(f"详细结果已保存到: {output_path}")
        print(f"  - backtest_result.json (详细数据)")
        print(f"  - backtest_report.txt (文本报告)")
        print(f"  - README.md (结果概览)")
        print()

        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断回测")
        return 1

    except Exception as e:
        logger.error(f"❌ 回测过程中发生错误: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
