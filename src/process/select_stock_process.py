# -*- coding: utf-8 -*-
"""
选股流程模块
封装main.py中的选股逻辑
"""

import time
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SelectStockProcess:
    """选股流程管理类 - 负责股票选择和分析"""

    def __init__(self, system=None, config=None):
        """
        初始化选股流程

        Args:
            system: A股TradingAgents系统实例
            config: 配置管理器实例
        """
        self.system = system
        self.config = config
        self.process_start_time = time.time()
        self.logger = logging.getLogger("SelectStockProcess")
        self.logger.info("🚀 选股流程开始初始化...")

    def execute_stock_selection(self) -> Tuple[List[Tuple[str, str]], Dict]:
        """
        执行股票选择流程

        Returns:
            (股票列表, 元数据信息)
        """
        stock_selection_start = time.time()
        self.logger.info("🎯 开始股票选择...")

        try:
            from config.config_manager import get_config
            from src.stock.stock_selection_manager import StockSelectionManager

            config = get_config()
            print("正在使用股票选择管理器...")

            # 初始化股票选择管理器
            stock_manager = StockSelectionManager(config)

            # 获取选股结果和元数据
            stock_list, metadata = stock_manager.get_selected_stocks()

            stock_selection_time = time.time() - stock_selection_start
            self.logger.info(f"✅ 股票选择完成，耗时: {stock_selection_time:.2f}秒")

            # 显示选股信息
            selection_method = metadata.get('selection_method', 'unknown')
            print(f"选股完成，方法: {selection_method}")
            print(f"共选择 {len(stock_list)} 只股票")
            self.logger.info(f"📊 选股结果: 方法={selection_method}, 数量={len(stock_list)}")

            # 显示来源分布（如果有）
            sources = metadata.get('sources', {})
            if sources:
                print("股票来源分布:")
                source_info = []
                for source, count in sources.items():
                    if count > 0:
                        print(f"  - {source}: {count} 只")
                        source_info.append(f"{source}={count}")
                self.logger.info(f"📊 股票来源分布: {', '.join(source_info)}")

            return stock_list, metadata

        except Exception as e:
            print(f"动态股票选择失败: {e}")
            print("使用传统配置文件股票列表...")
            try:
                from src.stock import get_all_stocks
                stock_list = get_all_stocks()[:20]  # 限制数量
                metadata = {
                    'selection_method': 'fallback_config',
                    'sources': {'config': len(stock_list)},
                    'total_selected': len(stock_list),
                    'error': str(e)
                }
            except ImportError:
                print("无法导入股票列表，使用默认列表")
                stock_list = []
                metadata = {
                    'selection_method': 'empty_list',
                    'sources': {},
                    'total_selected': 0,
                    'error': str(e)
                }

            return stock_list, metadata

    def execute_stock_analysis(self, stock_list: List[Tuple[str, str]],
                              price_limit_min: Optional[float] = None,
                              price_limit_max: Optional[float] = None) -> List[Dict]:
        """
        执行股票分析流程

        Args:
            stock_list: 股票列表 [(symbol, name), ...]
            price_limit_min: 价格下限
            price_limit_max: 价格上限

        Returns:
            分析结果列表
        """
        if not self.system:
            raise ValueError("系统实例未初始化，无法执行分析")

        analysis_start_time = time.time()
        self.logger.info("📈 股票分析阶段开始...")

        # 从配置获取价格限制
        config = self.config or get_config()
        price_limit_min = price_limit_min or config.get_price_limit_min()
        price_limit_max = price_limit_max or config.get_price_limit_max()
        enable_price_limits = config.get('analysis_settings.filters.enable_price_limits', False)

        print(f"\n准备分析 {len(stock_list)} 只A股股票...")
        self.logger.info(f"📊 准备分析{len(stock_list)}只股票")

        if enable_price_limits:
            print(f"价格筛选条件: 只分析价格{price_limit_min}元到{price_limit_max}元的股票")
            self.logger.info(f"💰 价格筛选: {price_limit_min}元-{price_limit_max}元")
        else:
            print("价格筛选: 已禁用，将分析所有价格区间的股票")
            self.logger.info("💰 价格筛选: 已禁用")

        print("正在获取数据和分析，请稍候...\n")

        # 执行批量分析（使用多线程版本）
        try:
            results = self.system.batch_analyze_threaded(stock_list, price_limit_min, price_limit_max)

            analysis_time = time.time() - analysis_start_time
            self.logger.info(f"✅ 股票分析完成，耗时: {analysis_time:.2f}秒")
            self.logger.info(f"📊 分析结果: 成功分析{len(results)}只股票")

            return results

        except Exception as e:
            self.logger.error(f"❌ 股票分析执行出错: {e}")
            raise

    def execute_learning_process(self):
        """执行历史学习流程"""
        if not self.system:
            self.logger.warning("系统实例未初始化，跳过学习流程")
            return

        if not self.system.enable_learning:
            self.logger.info("学习功能未启用，跳过学习流程")
            return

        try:
            print("\n正在从历史记录中学习...")
            learning_result = self.system.learn_from_history()
            if learning_result.get("success"):
                print("历史学习完成，已更新分析师权重")
                self.logger.info("✅ 历史学习完成")
            else:
                print(f"历史学习失败: {learning_result.get('error', '未知错误')}")
                self.logger.error(f"❌ 历史学习失败: {learning_result.get('error', '未知错误')}")
        except Exception as e:
            self.logger.error(f"学习流程执行失败: {e}")

    def execute_full_process(self) -> Dict:
        """
        执行完整的选股流程

        Returns:
            流程执行结果字典
        """
        self.logger.info("🚀 ================ 选股流程开始 ================")

        # 第一阶段：股票选择
        stock_list, metadata = self.execute_stock_selection()

        # 第二阶段：股票分析
        if stock_list:
            results = self.execute_stock_analysis(stock_list)

            # 第三阶段：输出结果
            if self.system:
                self.system.print_analysis_results(results)
        else:
            results = []
            print("没有股票可分析")

        # 第四阶段：学习流程
        self.execute_learning_process()

        # 计算总耗时
        total_time = time.time() - self.process_start_time
        self.logger.info(f"⏱️ 选股流程总耗时: {total_time:.2f}秒")
        if stock_list:
            self.logger.info(f"📊 平均每只股票: {total_time/len(stock_list):.2f}秒")

        return {
            'success': True,
            'stock_count': len(stock_list),
            'analysis_count': len(results),
            'total_time': total_time,
            'metadata': metadata,
            'results': results
        }