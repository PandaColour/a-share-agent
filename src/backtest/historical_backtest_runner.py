# -*- coding: utf-8 -*-
"""
历史回测运行器 - 集成AI因子分析系统的完整历史回测

对历史数据进行逐日分析，生成交易决策，然后使用回测引擎计算收益
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging

from .advanced_backtest_engine import AdvancedBacktestEngine
from .data_collector import BacktestDataCollector

logger = logging.getLogger(__name__)


class HistoricalBacktestRunner:
    """
    历史回测运行器

    核心功能：
    1. 复用现有选股系统获取股票池
    2. 对历史数据逐日运行AI因子分析
    3. 生成历史交易决策
    4. 使用回测引擎模拟交易并计算收益
    """

    def __init__(self, trading_system):
        """
        初始化历史回测运行器

        Args:
            trading_system: TradingSystem 实例（包含AI因子、风险管理、选股系统等）
        """
        self.system = trading_system
        self.backtest_engine = AdvancedBacktestEngine(config_manager=trading_system.config_manager)
        self.data_collector = BacktestDataCollector()

        # 股票名称映射 {symbol: name}
        self.symbol_to_name = {}

        logger.info("历史回测运行器初始化完成")

    def run_historical_backtest(self,
                               symbols: List[str] = None,
                               start_date: str = None,
                               end_date: str = None,
                               months_back: int = 3,
                               initial_capital: float = None) -> Dict:
        """
        运行历史回测

        Args:
            symbols: 股票列表，None则使用选股系统
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            months_back: 向前回测月数（如果未指定日期）
            initial_capital: 初始资金，None则使用配置

        Returns:
            回测结果字典
        """
        try:
            # 步骤1: 确定股票池（复用选股系统）
            if symbols is None:
                symbols = self._get_stock_pool()

            if not symbols:
                return {"error": "没有可用的股票进行回测"}

            logger.info(f"回测股票池: {len(symbols)} 只股票")

            # 步骤2: 确定回测时间范围
            if end_date is None:
                end_date = datetime.now().strftime("%Y-%m-%d")
            if start_date is None:
                start_dt = datetime.now() - timedelta(days=30 * months_back)
                start_date = start_dt.strftime("%Y-%m-%d")

            logger.info(f"回测时间范围: {start_date} 至 {end_date}")

            # 步骤3: 收集历史数据
            logger.info("开始收集历史数据...")
            historical_data = self._collect_historical_data(symbols, start_date, end_date)

            if not historical_data:
                return {"error": "没有收集到历史数据"}

            logger.info(f"成功收集 {len(historical_data)} 只股票的历史数据")

            # 步骤4: 生成交易日列表
            trading_dates = self._get_trading_dates(start_date, end_date)
            logger.info(f"回测交易日数量: {len(trading_dates)} 天")

            # 步骤5: 逐日分析生成历史决策（关键步骤！）
            logger.info("开始逐日历史分析，生成交易决策...")
            recommendations = self._generate_historical_recommendations(
                trading_dates, symbols, historical_data
            )

            logger.info(f"生成历史决策: {len(recommendations)} 条")

            if not recommendations:
                return {"error": "没有生成任何交易决策"}

            # 步骤6: 使用回测引擎执行回测
            logger.info("开始执行回测模拟...")

            # 设置初始资金
            if initial_capital:
                self.backtest_engine.initial_capital = initial_capital
                self.backtest_engine.current_capital = initial_capital

            results = self.backtest_engine.run_strategy_backtest(
                recommendations, historical_data
            )

            # 添加回测配置信息到结果
            results['backtest_config'] = {
                'start_date': start_date,
                'end_date': end_date,
                'stock_count': len(symbols),
                'trading_days': len(trading_dates),
                'decision_count': len(recommendations),
                'initial_capital': self.backtest_engine.initial_capital
            }

            # 添加股票名称映射
            results['symbol_to_name'] = self.symbol_to_name

            # 添加历史数据（用于生成K线图）
            results['historical_data'] = historical_data

            logger.info(f"回测完成！总收益率: {results.get('total_return', 0):.2%}")

            return results

        except Exception as e:
            logger.error(f"历史回测执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def _get_stock_pool(self) -> List[str]:
        """
        获取股票池（复用现有选股系统）

        Returns:
            股票代码列表
        """
        try:
            # 导入选股管理器
            from src.stock.stock_selection_manager import StockSelectionManager

            # 创建选股管理器实例
            stock_selection_manager = StockSelectionManager(self.system.config_manager)

            # 调用选股系统，自动处理缓存
            # 如果 config/dynamic_stock.json 是今天的，就用缓存
            # 如果不是今天的，会自动重新选股
            stock_tuples, metadata = stock_selection_manager.get_selected_stocks()

            # 提取股票代码和名称
            symbols = []
            for symbol, name in stock_tuples:
                symbols.append(symbol)
                self.symbol_to_name[symbol] = name  # 保存股票名称映射

            logger.info(f"从选股系统获取股票池: {len(symbols)} 只")
            logger.info(f"选股方法: {metadata.get('selection_method', 'unknown')}")
            logger.info(f"选股时间: {metadata.get('selection_time', 'unknown')}")

            return symbols

        except Exception as e:
            logger.error(f"获取股票池失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _collect_historical_data(self,
                                symbols: List[str],
                                start_date: str,
                                end_date: str) -> Dict[str, pd.DataFrame]:
        """
        收集所有股票的历史数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            {symbol: DataFrame} 字典
        """
        historical_data = {}

        # 向前扩展60天，确保有足够的历史数据用于计算指标
        extended_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")

        for symbol in symbols:
            try:
                data = self.data_collector.get_price_data(symbol, extended_start, end_date)

                if data is not None and not data.empty and len(data) >= 60:
                    historical_data[symbol] = data
                    logger.debug(f"收集 {symbol} 数据: {len(data)} 条记录")
                else:
                    logger.warning(f"股票 {symbol} 数据不足，跳过")

            except Exception as e:
                logger.warning(f"收集 {symbol} 数据失败: {e}")
                continue

        return historical_data

    def _get_trading_dates(self, start_date: str, end_date: str) -> List[pd.Timestamp]:
        """
        生成交易日列表（工作日）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            交易日时间戳列表
        """
        all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
        # 过滤周末（周一=0, 周日=6）
        trading_dates = [d for d in all_dates if d.weekday() < 5]
        return trading_dates

    def _generate_historical_recommendations(self,
                                            trading_dates: List[pd.Timestamp],
                                            symbols: List[str],
                                            historical_data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        逐日生成历史交易决策

        这是核心方法！模拟"站在历史某一天"做分析和决策

        Args:
            trading_dates: 交易日列表
            symbols: 股票代码列表
            historical_data: 历史数据字典

        Returns:
            推荐列表
        """
        all_recommendations = []
        total_days = len(trading_dates)

        logger.info(f"开始逐日分析: 共 {total_days} 个交易日")

        for day_idx, current_date in enumerate(trading_dates, 1):
            # 每10天打印一次进度
            if day_idx % 10 == 0 or day_idx == 1:
                progress = (day_idx / total_days) * 100
                logger.info(f"分析进度: {day_idx}/{total_days} ({progress:.1f}%) - {current_date.strftime('%Y-%m-%d')}")

            # 分析当日的所有股票
            daily_recs = self._analyze_trading_day(current_date, symbols, historical_data)
            all_recommendations.extend(daily_recs)

        logger.info(f"历史分析完成，共生成 {len(all_recommendations)} 条决策")

        return all_recommendations

    def _analyze_trading_day(self,
                            current_date: pd.Timestamp,
                            symbols: List[str],
                            historical_data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        分析单个交易日（使用截至当日的数据）

        关键：只使用当日及之前的数据，避免未来数据泄露！

        Args:
            current_date: 当前交易日
            symbols: 股票列表
            historical_data: 全部历史数据

        Returns:
            当日的推荐列表
        """
        daily_recommendations = []
        date_str = current_date.strftime("%Y-%m-%d")

        for symbol in symbols:
            if symbol not in historical_data:
                continue

            try:
                # 关键：只使用截至当日的历史数据（避免未来信息泄露）
                full_data = historical_data[symbol]
                data_up_to_date = full_data[full_data.index <= current_date]

                # 数据不足，跳过
                if len(data_up_to_date) < 60:
                    continue

                # 检查当日是否有数据（可能停牌）
                if current_date not in data_up_to_date.index:
                    continue

                # 运行完整的AI因子分析流程
                analysis_result = self._run_ai_factor_analysis(symbol, data_up_to_date)

                if not analysis_result:
                    continue

                # 运行风险评估
                risk_assessment = self._run_risk_assessment(data_up_to_date)

                # 获取当日价格信息
                current_price = data_up_to_date.iloc[-1]['Close']
                daily_high = data_up_to_date.iloc[-1]['High']
                daily_low = data_up_to_date.iloc[-1]['Low']

                price_info = {
                    "current_price": current_price,
                    "daily_high": daily_high,
                    "daily_low": daily_low,
                    "daily_change": 0,
                    "daily_change_percent": 0
                }

                # 生成交易决策
                decision = self.system.portfolio_manager.make_decision(
                    symbol,
                    [analysis_result],
                    risk_assessment,
                    price_info
                )

                # 只记录买入和卖出信号（持有信号不生成交易）
                if decision.action in ["买入", "卖出"]:
                    daily_recommendations.append({
                        "symbol": symbol,
                        "recommendation": decision.action,
                        "confidence": decision.confidence,
                        "analysis_time": f"{date_str} 09:30:00",  # 假设早盘分析
                        "price": current_price,
                        "reason": decision.reason
                    })

            except Exception as e:
                logger.debug(f"分析 {symbol} 在 {date_str} 失败: {e}")
                continue

        return daily_recommendations

    def _run_ai_factor_analysis(self, symbol: str, data: pd.DataFrame) -> Optional[Dict]:
        """
        运行AI因子分析（复用系统的分析方法）

        Args:
            symbol: 股票代码
            data: 历史数据

        Returns:
            AI因子分析结果
        """
        try:
            # 直接调用系统的AI因子分析方法
            indicators = {}  # 可以为空，AI因子不依赖技术指标

            analysis_result = self.system._ai_factor_analysis(symbol, data, indicators)

            return analysis_result

        except Exception as e:
            logger.debug(f"AI因子分析失败 {symbol}: {e}")
            return None

    def _run_risk_assessment(self, data: pd.DataFrame) -> Dict:
        """
        运行风险评估（复用系统的风险管理）

        Args:
            data: 历史数据

        Returns:
            风险评估结果
        """
        try:
            # 计算基本的风险指标
            indicators = {}

            # 计算波动率
            if len(data) >= 20:
                returns = data['Close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)  # 年化波动率
                indicators['volatility'] = volatility

            # 调用风险管理器
            risk_assessment = self.system.risk_manager.assess_risk(data, indicators)

            return risk_assessment

        except Exception as e:
            logger.debug(f"风险评估失败: {e}")
            # 返回默认的中等风险
            return {
                "risk_score": 0.5,
                "risk_level": "中等",
                "risk_factors": []
            }
