# -*- coding: utf-8 -*-
"""
因子IC评估主执行脚本
整合数据收集和IC计算，生成完整的评估报告
"""

import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

import logging
from datetime import datetime
from pathlib import Path

from src.factors.factor_ic_evaluator import FactorICEvaluator
from src.factors.factor_data_collector import FactorDataCollector
from src.factors.factor_manager import FactorManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FactorICEvaluationPipeline:
    """因子IC评估流水线"""

    def __init__(self):
        """初始化评估流水线"""
        self.data_collector = FactorDataCollector()
        self.ic_evaluator = FactorICEvaluator()
        self.factor_manager = FactorManager()

        logger.info("IC评估流水线初始化完成")

    def step1_collect_data(self,
                          symbols: list = None,
                          days: int = 60,
                          use_cache: bool = True) -> bool:
        """
        步骤1：收集数据

        Args:
            symbols: 股票列表（如果为None，使用默认股票池）
            days: 收集天数
            use_cache: 是否使用缓存数据

        Returns:
            是否成功
        """
        logger.info("\n" + "="*60)
        logger.info("步骤1：数据收集")
        logger.info("="*60)

        # 尝试加载缓存
        if use_cache and self.data_collector.load_from_disk():
            logger.info("✓ 使用缓存数据")

            # 检查数据是否足够
            summary = self.data_collector.get_summary()
            if summary['num_dates'] >= 40:  # 至少40天数据
                logger.info(f"✓ 缓存数据充足: {summary['num_dates']}天")
                return True
            else:
                logger.warning(f"⚠ 缓存数据不足: {summary['num_dates']}天，需要重新收集")

        # 获取股票列表
        if symbols is None:
            # 从配置或默认股票池获取
            from config.config_manager import get_config
            config = get_config()
            symbols = config.get('stock_selection', {}).get('manual_selections', [])

            if not symbols:
                # 使用一些默认股票
                symbols = [
                    '000001.SZ',  # 平安银行
                    '600519.SH',  # 贵州茅台
                    '000002.SZ',  # 万科A
                    '600036.SH',  # 招商银行
                    '000333.SZ',  # 美的集团
                ]
                logger.info(f"使用默认股票池: {len(symbols)}只")

        logger.info(f"开始收集数据: {len(symbols)}只股票, {days}天")

        # 模拟数据收集
        collected_days = self.data_collector.simulate_data_collection(
            symbols=symbols,
            days=days,
            factor_manager=self.factor_manager
        )

        if collected_days < 20:
            logger.error(f"❌ 数据收集失败，只收集到{collected_days}天")
            return False

        # 保存到磁盘
        self.data_collector.save_to_disk()

        logger.info(f"✓ 数据收集完成: {collected_days}天")
        return True

    def step2_calculate_ic(self) -> bool:
        """
        步骤2：计算IC

        Returns:
            是否成功
        """
        logger.info("\n" + "="*60)
        logger.info("步骤2：计算IC")
        logger.info("="*60)

        # 获取所有因子名称
        factor_names = list(self.data_collector.factor_value_history.keys())

        if not factor_names:
            logger.error("❌ 没有因子数据")
            return False

        logger.info(f"发现 {len(factor_names)} 个因子")

        # 获取所有日期
        dates = self.data_collector.get_available_dates()

        if len(dates) < 20:
            logger.error(f"❌ 日期数量不足: {len(dates)}天")
            return False

        logger.info(f"计算时间范围: {dates[0]} 到 {dates[-1]} ({len(dates)}天)")

        # 逐日计算IC
        ic_calculated = 0

        for date in dates:
            # 获取次日收益率
            returns = self.data_collector.get_returns_by_date(date)

            if not returns:
                logger.debug(f"  {date}: 无收益率数据，跳过")
                continue

            # 为每个因子计算IC
            for factor_name in factor_names:
                factor_values = self.data_collector.get_factor_values_by_date(factor_name, date)

                if not factor_values:
                    continue

                # 计算IC
                ic_value = self.ic_evaluator.calculate_daily_ic(
                    factor_values,
                    returns,
                    date
                )

                # 计算Rank IC
                rank_ic = self.ic_evaluator.calculate_rank_ic(
                    factor_values,
                    returns
                )

                # 更新IC历史
                self.ic_evaluator.update_ic_history(
                    factor_name,
                    date,
                    ic_value,
                    rank_ic
                )

            ic_calculated += 1

            if ic_calculated % 10 == 0:
                logger.info(f"  已计算 {ic_calculated}/{len(dates)} 天")

        logger.info(f"✓ IC计算完成: {ic_calculated}天")
        return True

    def step3_evaluate_factors(self, window: int = 60) -> dict:
        """
        步骤3：评估因子

        Args:
            window: 评估窗口

        Returns:
            评估结果字典
        """
        logger.info("\n" + "="*60)
        logger.info("步骤3：评估因子")
        logger.info("="*60)

        # 获取所有因子名称
        factor_names = list(self.factor_manager.factors.keys())

        if not factor_names:
            logger.warning("⚠ 因子管理器中没有注册因子，尝试从数据中提取")
            factor_names = list(self.data_collector.factor_value_history.keys())

        logger.info(f"评估 {len(factor_names)} 个因子...")

        # 批量评估
        results = self.ic_evaluator.batch_evaluate_all_factors(
            factor_names,
            window=window
        )

        logger.info(f"✓ 因子评估完成")
        return results

    def step4_generate_report(self, evaluation_results: dict) -> str:
        """
        步骤4：生成报告

        Args:
            evaluation_results: 评估结果

        Returns:
            报告文件路径
        """
        logger.info("\n" + "="*60)
        logger.info("步骤4：生成报告")
        logger.info("="*60)

        # 生成Markdown报告
        markdown_report = self.ic_evaluator.generate_evaluation_report(
            evaluation_results,
            output_format='markdown'
        )

        # 生成JSON报告
        json_report = self.ic_evaluator.generate_evaluation_report(
            evaluation_results,
            output_format='json'
        )

        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d')
        report_dir = Path("factor_cache/ic_evaluation")
        report_dir.mkdir(parents=True, exist_ok=True)

        # 保存Markdown
        md_file = report_dir / f"factor_report_{timestamp}.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(markdown_report)

        # 保存JSON
        json_file = report_dir / f"factor_report_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(json_report)

        logger.info(f"✓ Markdown报告: {md_file}")
        logger.info(f"✓ JSON报告: {json_file}")

        # 打印关键结论
        self._print_key_findings(evaluation_results)

        return str(md_file)

    def _print_key_findings(self, results: dict):
        """打印关键发现"""
        logger.info("\n" + "="*60)
        logger.info("关键发现")
        logger.info("="*60)

        # 统计
        ratings = {'A+': [], 'A': [], 'B': [], 'C': [], 'D': [], 'F': []}

        for name, result in results.items():
            if 'rating' in result:
                rating = result['rating']
                if rating in ratings:
                    ratings[rating].append(name)

        # 打印统计
        logger.info(f"\n📊 评级分布:")
        logger.info(f"  ⭐⭐⭐⭐⭐ A+级 ({len(ratings['A+'])}个): {', '.join(ratings['A+']) if ratings['A+'] else '无'}")
        logger.info(f"  ⭐⭐⭐⭐   A级  ({len(ratings['A'])}个): {', '.join(ratings['A']) if ratings['A'] else '无'}")
        logger.info(f"  ⭐⭐⭐     B级  ({len(ratings['B'])}个): {', '.join(ratings['B']) if ratings['B'] else '无'}")
        logger.info(f"  ⭐⭐       C级  ({len(ratings['C'])}个): {', '.join(ratings['C']) if ratings['C'] else '无'}")
        logger.info(f"  ⭐         D级  ({len(ratings['D'])}个): {', '.join(ratings['D']) if ratings['D'] else '无'}")
        logger.info(f"  ❌         F级  ({len(ratings['F'])}个): {', '.join(ratings['F']) if ratings['F'] else '无'}")

        # 淘汰建议
        to_eliminate = []
        to_downweight = []

        for name, result in results.items():
            if result.get('recommendation') in ['eliminate', 'eliminate_immediately']:
                to_eliminate.append(name)
            elif result.get('recommendation') == 'downweight':
                to_downweight.append(name)

        logger.info(f"\n💡 优化建议:")
        if to_eliminate:
            logger.info(f"  ❌ 建议淘汰 ({len(to_eliminate)}个): {', '.join(to_eliminate)}")
        if to_downweight:
            logger.info(f"  ⚠️  降权观察 ({len(to_downweight)}个): {', '.join(to_downweight)}")

        if not to_eliminate and not to_downweight:
            logger.info(f"  ✓ 所有因子表现良好，无需淘汰")

    def run_full_pipeline(self,
                         symbols: list = None,
                         days: int = 60,
                         window: int = 60,
                         use_cache: bool = True) -> str:
        """
        运行完整评估流程

        Args:
            symbols: 股票列表
            days: 数据收集天数
            window: 评估窗口
            use_cache: 是否使用缓存

        Returns:
            报告文件路径
        """
        logger.info("\n" + "="*60)
        logger.info("因子IC评估 - 完整流程")
        logger.info("="*60)

        # 步骤1：收集数据
        if not self.step1_collect_data(symbols, days, use_cache):
            logger.error("❌ 数据收集失败，流程终止")
            return None

        # 步骤2：计算IC
        if not self.step2_calculate_ic():
            logger.error("❌ IC计算失败，流程终止")
            return None

        # 步骤3：评估因子
        results = self.step3_evaluate_factors(window)

        if not results:
            logger.error("❌ 因子评估失败，流程终止")
            return None

        # 步骤4：生成报告
        report_path = self.step4_generate_report(results)

        logger.info("\n" + "="*60)
        logger.info("✓ 评估流程完成！")
        logger.info(f"✓ 报告路径: {report_path}")
        logger.info("="*60)

        return report_path


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='因子IC评估工具')
    parser.add_argument('--days', type=int, default=60, help='数据收集天数')
    parser.add_argument('--window', type=int, default=60, help='评估窗口大小')
    parser.add_argument('--no-cache', action='store_true', help='不使用缓存数据')
    parser.add_argument('--symbols', nargs='+', help='指定股票代码列表')

    args = parser.parse_args()

    # 运行评估
    pipeline = FactorICEvaluationPipeline()

    report_path = pipeline.run_full_pipeline(
        symbols=args.symbols,
        days=args.days,
        window=args.window,
        use_cache=not args.no_cache
    )

    if report_path:
        print(f"\n✓ 评估完成！")
        print(f"✓ 报告位置: {report_path}")
        print(f"\n请查看报告了解详细评估结果")
    else:
        print("\n❌ 评估失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
