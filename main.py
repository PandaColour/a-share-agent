#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于TradingAgents的A股量化交易系统主程序
"""

import os
import sys

# 禁用 scikit-learn/joblib 的并行功能，避免 Windows 兼容性问题
# 我们使用自己的 ThreadPoolExecutor 来实现并行
os.environ['LOKY_MAX_CPU_COUNT'] = '1'  # 禁用 joblib 并行
os.environ['JOBLIB_MULTIPROCESSING'] = '0'  # 禁用 joblib 多进程
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import json
import pandas as pd
import numpy as np
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import warnings
import logging
from logging.handlers import RotatingFileHandler

from src.trade.decision import TradingDecision

# Add config directory to path
config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
sys.path.insert(0, config_dir)

# 配置日志系统
def setup_logging():
    """配置日志系统，输出到文件和控制台"""
    # 确保logs目录存在
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 文件处理器 - 主系统日志
    log_file = os.path.join(log_dir, 'trading_system.log')
    file_handler = RotatingFileHandler(
        log_file, maxBytes=50*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)

    # AI因子系统日志
    ai_log_file = os.path.join(log_dir, 'ai_factor_system.log')
    ai_file_handler = RotatingFileHandler(
        ai_log_file, maxBytes=50*1024*1024, backupCount=5, encoding='utf-8'
    )
    ai_file_handler.setLevel(logging.INFO)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler.setFormatter(formatter)
    ai_file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # AI因子系统使用单独的日志文件
    ai_logger = logging.getLogger('factors')
    ai_logger.addHandler(ai_file_handler)
    ai_logger.propagate = False  # 避免重复日志

    return root_logger

# 初始化日志系统
logger = setup_logging()

try:
    from config_manager import get_config
except ImportError:
    def get_config():
        return None

warnings.filterwarnings('ignore')

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from agents.risk_manager import RiskManager
    from agents.portfolio_manager import PortfolioManager
    from data.data_provider import AShareDataProvider
    from trade.decision import TradingDecision
    from output.analysis_output_manager import AnalysisOutputManager
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖文件都已正确创建")
    sys.exit(1)

class AShareTradingAgentsSystem:
    """A股TradingAgents系统主类"""
    
    def __init__(self, config_manager=None):
        """初始化系统"""
        self.logger = logging.getLogger("AShareTradingSystem")

        # 系统启动时间统计
        self.system_start_time = time.time()
        self.logger.info("🚀 A股TradingAgents系统开始初始化...")
        
        # 使用统一配置
        self.config = config_manager or get_config()
        self.config_manager = self.config  # 兼容性别名
        self.max_workers = self.config.get_max_workers()

        # 主线程组件
        self.data_provider = AShareDataProvider()
        self.risk_manager = RiskManager()
        # 初始化投资组合管理器
        self.portfolio_manager = PortfolioManager()
        
        # 禁用多线程分析器和记忆学习系统（已删除相关模块）
        self.memory_system = None
        self.enable_learning = False
        
        # AI因子系统初始化
        self.ai_factor_enabled = False
        self.factor_manager = None
        try:
            from src.factors import initialize_factors, get_factor_manager, get_auto_factor_summary
            initialize_factors(enable_auto_generation=True)  # 启用自动因子生成
            self.factor_manager = get_factor_manager()
            self.ai_factor_enabled = True
            
            # 获取因子详情
            total_factors = len(self.factor_manager.factors)
            factor_names = list(self.factor_manager.factors.keys())
            
            self.logger.info(f"AI因子系统初始化成功，已注册 {total_factors} 个因子")
            self.logger.info(f"因子列表: {', '.join(factor_names)}")
            
            # 显示自动生成因子的摘要
            try:
                auto_summary = get_auto_factor_summary()
                if auto_summary.get("total_factors", 0) > 0:
                    self.logger.info(f"其中自动生成因子 {auto_summary['total_factors']} 个")
            except Exception:
                pass
                
        except ImportError as e:
            self.logger.warning(f"AI因子系统初始化失败: {e}")
        
        # 线程本地存储，用于为每个线程创建独立的组件实例
        self._thread_local = threading.local()

        # 初始化输出管理器
        self.output_manager = AnalysisOutputManager()

        # 计算初始化耗时
        init_time = time.time() - self.system_start_time
        self.logger.info(f"✅ A股TradingAgents系统初始化完成，耗时: {init_time:.2f}秒")
        self.logger.info(f"📊 系统配置: {self.max_workers}个并行线程, AI因子{'已启用' if self.ai_factor_enabled else '已禁用'}")


    def _get_thread_components(self):
        """获取线程本地组件实例(确保线程安全)"""
        if not hasattr(self._thread_local, 'components'):
            # 为每个线程创建独立的组件实例
            self._thread_local.components = {
                'data_provider': AShareDataProvider(),
                'risk_manager': RiskManager(),
                'portfolio_manager': PortfolioManager()
            }

        return self._thread_local.components

    def _get_cached_analysis_components(self):
        """获取用于缓存数据分析的轻量级组件（不包含数据提供者）"""
        try:
            from src.data.cached_analysis_components import get_cached_analysis_components
            return get_cached_analysis_components()
        except ImportError as e:
            self.logger.warning(f"缓存分析组件不可用，回退到完整组件: {e}")
            # 回退到原有的完整组件，但移除data_provider避免重复初始化
            components = self._get_thread_components()
            return {k: v for k, v in components.items() if k != 'data_provider'}
        
    def analyze_stock(self, symbol: str, stock_name: str = None, price_limit_min: float = None,
                     price_limit_max: float = None, use_thread_safe: bool = False) -> TradingDecision:
        """分析单只股票"""
        # 选择使用主线程组件还是线程安全组件
        if use_thread_safe:
            components = self._get_thread_components()
            data_provider = components['data_provider']
            risk_manager = components['risk_manager']
            portfolio_manager = components['portfolio_manager']
        else:
            data_provider = self.data_provider
            risk_manager = self.risk_manager
            portfolio_manager = self.portfolio_manager

        # 0. 初始化TradingDecision记录分析状态
        from datetime import datetime
        initial_decision = TradingDecision(
            action="分析中",
            confidence=0.0,
            reason="正在分析...",
            risk_level="未知",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            analysis_status="initialized"
        )
        self.logger.info(f"🔍 已初始化TradingDecision，开始分析: {symbol}")

        # 1. 数据获取
        initial_decision.analysis_status = "in_progress"
        data, info, indicators, price_info = data_provider.get_stock_data(symbol)

        if data is None or data.empty:
            self.logger.error(f"无法获取股票数据: {symbol}")
            return TradingDecision(
                action="错误",
                confidence=0.0,
                reason="数据获取失败",
                risk_level="未知",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                current_price=price_info.get("current_price", 0.0),
                daily_high=price_info.get("daily_high", 0.0),
                daily_low=price_info.get("daily_low", 0.0),
                daily_change=price_info.get("daily_change", 0.0),
                daily_change_percent=price_info.get("daily_change_percent", 0.0)
            )
        
        # 2. 创业板过滤检查
        if self.config_manager.get_exclude_chinext():
            if self._is_chinext_stock(symbol):
                self.logger.info(f"跳过创业板股票: {stock_name or symbol}({symbol})")
                return TradingDecision(
                    action="跳过",
                    confidence=0.0,
                    reason="创业板股票已被排除",
                    risk_level="未知",
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    current_price=price_info.get("current_price", 0.0),
                    daily_high=price_info.get("daily_high", 0.0),
                    daily_low=price_info.get("daily_low", 0.0),
                    daily_change=price_info.get("daily_change", 0.0),
                    daily_change_percent=price_info.get("daily_change_percent", 0.0)
                )
        
        # 3. 价格过滤检查（可选）
        enable_price_limits = self.config_manager.get('analysis_settings.filters.enable_price_limits', False)
        if enable_price_limits:
            current_price = price_info.get("current_price", 0.0)
            if (price_limit_min and current_price < price_limit_min) or (price_limit_max and current_price > price_limit_max):
                price_range = ""
                if price_limit_min and price_limit_max:
                    price_range = f"{price_limit_min}元到{price_limit_max}元"
                elif price_limit_min:
                    price_range = f">= {price_limit_min}元"
                elif price_limit_max:
                    price_range = f"<= {price_limit_max}元"
                self.logger.info(f"股票价格{current_price:.2f}不在限制范围{price_range}内，跳过分析: {stock_name or symbol}")
                return TradingDecision(
                    action="跳过",
                    confidence=0.0,
                    reason=f"价格{current_price:.2f}元不在限制范围{price_range}内",
                    risk_level="未知",
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    current_price=current_price,
                    daily_high=price_info.get("daily_high", 0.0),
                    daily_low=price_info.get("daily_low", 0.0),
                    daily_change=price_info.get("daily_change", 0.0),
                    daily_change_percent=price_info.get("daily_change_percent", 0.0)
                )
        
        # 4. AI因子分析
        analyses = []
        analysis_failures = []

        # 准备分析师输入信息
        analyst_inputs = {
            "symbol": symbol,
            "data_shape": data.shape if data is not None else "N/A",
            "data_date_range": f"{data.index[0].strftime('%Y-%m-%d')} 到 {data.index[-1].strftime('%Y-%m-%d')}" if data is not None and not data.empty else "N/A",
            "info_keys": list(info.keys()) if info else [],
            "indicators_keys": list(indicators.keys()) if indicators else [],
            "current_price": price_info.get("current_price", 0.0),
            "analysis_timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # AI因子分析
        ai_factor_analysis = None
        if self.ai_factor_enabled and self.factor_manager:
            try:
                ai_factor_analysis = self._ai_factor_analysis(symbol, data, indicators)
                if ai_factor_analysis:
                    ai_factor_analysis["analyst_inputs"] = analyst_inputs.copy()
                    analyses.append(ai_factor_analysis)
                    self.logger.info(f"AI因子分析完成: {symbol}")
            except Exception as e:
                self.logger.error(f"AI因子分析失败 {symbol}: {e}")
                analysis_failures.append("AI因子分析失败")

        # 检查AI因子分析是否失败
        if len(analysis_failures) > 0 or len(analyses) == 0:
            self.logger.warning(f"AI因子分析失败 {symbol}: {', '.join(analysis_failures) if analysis_failures else '无分析结果'}")
            return TradingDecision(
                action="分析失败",
                confidence=0.0,
                reason=f"AI因子分析失败: {', '.join(analysis_failures) if analysis_failures else '无分析结果'}。建议检查AI模型配置、网络连接或数据源",
                risk_level="未知",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        
        # 3. 风险评估
        risk_assessment = risk_manager.assess_risk(
            data=data,
            indicators=indicators,
            symbol=symbol,
            analyses=analyses
        )

        # 4. 最终决策 (应用信号过滤)
        self.logger.info(f"🔍 开始最终决策，分析师数量: {len(analyses)}")
        decision = portfolio_manager.make_decision(
            symbol, analyses, risk_assessment, price_info,
            data=data,  # 【新增】传入历史数据用于信号过滤
            position_info=None  # 正常预测无持仓信息
        )
        self.logger.info(f"🔍 最终决策完成: {symbol}, action={decision.action}")
        self.logger.info(f"🔍 决策对象中是否包含多轮辩论结果: {hasattr(decision, 'multi_round_debate_result') and decision.multi_round_debate_result is not None}")
        
        # 检查决策是否失败
        if decision.action in ["无法决策", "分析失败"]:
            self.logger.warning(f"决策失败 {symbol}: {decision.reason}")
        
        # 5. 记录决策到记忆系统
        if (self.enable_learning and self.memory_system and 
            decision.action not in ["无法决策", "分析失败"]):
            self.record_trading_decision(symbol, decision, analyses)
        
        self.logger.debug(f"分析完成: {stock_name or symbol} -> {decision.action}")
        return decision
    
    def record_trading_decision(self, symbol: str, decision: TradingDecision, analyses: List[Dict]):
        """记录交易决策到记忆系统"""
        try:
            # 收集分析师的表现数据
            analyst_performances = {}
            for analysis in analyses:
                analyst_type = analysis.get("analyst_type", "")
                if analyst_type:
                    analyst_performances[analyst_type] = {
                        "confidence": analysis.get("confidence", 0.5),
                        "recommendation": analysis.get("recommendation", "持有"),
                        "reasoning": analysis.get("reasoning", [])
                    }
            
            # 记录到记忆系统
            reasons = [decision.reason] if decision.reason else []
            market_context = {
                "risk_level": decision.risk_level,
                "current_price": decision.current_price,
                "daily_change": decision.daily_change_percent,
                "timestamp": decision.timestamp
            }
            
            self.memory_system.remember_decision(
                symbol=symbol,
                decision=decision.action,
                confidence=decision.confidence,
                reasons=reasons,
                analyses=list(analyst_performances.values()),
                market_context=market_context
            )
            
            self.logger.debug(f"已记录决策到记忆系统: {symbol} -> {decision.action}")
            
        except Exception as e:
            self.logger.error(f"记录决策失败: {e}")
    
    def learn_from_history(self, symbol: str = None) -> Dict:
        """从历史记录中学习"""
        if not self.enable_learning or not self.memory_system:
            return {"message": "记忆学习系统未启用"}
        
        try:
            # 获取学习见解
            insights = self.memory_system.get_learning_insights(symbol)
            
            # 应用动态权重调整
            if insights.get("analyst_performance"):
                self._apply_dynamic_weights(insights["analyst_performance"])
            
            return {
                "success": True,
                "insights": insights,
                "message": f"已从历史记录中学习{'(' + symbol + ')' if symbol else ''}"
            }
            
        except Exception as e:
            self.logger.error(f"从历史记录学习失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _apply_dynamic_weights(self, analyst_performance: Dict):
        """根据分析师历史表现动态调整权重"""
        try:
            # 获取各分析师的平均准确率
            total_weight = 0
            new_weights = {}
            
            for analyst_type, performance in analyst_performance.items():
                accuracy = performance.get("accuracy", 0.5)
                # 基于准确率调整权重，准确率越高权重越大
                weight = max(0.1, accuracy * 0.6)  # 最低权重0.1，最高权重0.6
                new_weights[analyst_type] = weight
                total_weight += weight
            
            # 归一化权重
            if total_weight > 0:
                for analyst_type in new_weights:
                    new_weights[analyst_type] = new_weights[analyst_type] / total_weight
                
                # 更新投资组合管理器的权重
                self.portfolio_manager.decision_weights.update(new_weights)
                
                self.logger.info(f"已更新分析师权重: {new_weights}")
                
        except Exception as e:
            self.logger.error(f"动态权重调整失败: {e}")
    
    def _progress_callback(self, completed: int, total: int, current_stock_name: str):
        """进度回调函数"""
        progress_percent = (completed / total) * 100
        print(f"  分析进度: [{completed}/{total}] {current_stock_name} ({progress_percent:.1f}%)")
    
    def _analyze_stock_with_cache(self, symbol: str, name: str, price_limit_min: Optional[float],
                                 price_limit_max: Optional[float], data_cache: Dict[str, Dict]) -> Dict:
        """使用缓存数据进行线程安全的股票分析（分离版本）"""
        import time
        start_time = time.time()

        # 初始化TradingDecision跟踪分析状态
        from datetime import datetime
        analysis_status = {
            "symbol": symbol,
            "start_time": start_time,
            "status": "initialized",
            "multi_round_debate_checked": False
        }
        self.logger.info(f"🔍 [缓存分析] 开始分析股票: {symbol}, 初始化状态跟踪")

        try:
            # 从缓存中获取数据
            cached_data = data_cache.get(symbol)
            if not cached_data or not cached_data.get('success'):
                return {
                    "股票代码": symbol,
                    "股票名称": name,
                    "操作建议": "错误",
                    "信心度": "0%",
                    "风险等级": "未知",
                    "当前价格": "N/A",
                    "当日最高": "N/A",
                    "当日最低": "N/A",
                    "当日涨跌": "N/A",
                    "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "决策理由": f"缓存数据无效: {cached_data.get('error', '未知原因') if cached_data else '数据不存在'}"
                }
            
            data = cached_data['data']
            info = cached_data['info']
            indicators = cached_data['indicators']
            price_info = cached_data['price_info']
            
            # 创业板过滤检查
            if self.config_manager.get_exclude_chinext():
                if self._is_chinext_stock(symbol):
                    return {
                        "股票代码": symbol,
                        "股票名称": name,
                        "操作建议": "跳过",
                        "信心度": "0%",
                        "风险等级": "未知",
                        "当前价格": f"{price_info.get('current_price', 0.0):.2f}元",
                        "当日最高": f"{price_info.get('daily_high', 0.0):.2f}元",
                        "当日最低": f"{price_info.get('daily_low', 0.0):.2f}元",
                        "当日涨跌": f"+{price_info.get('daily_change_percent', 0.0):.2f}%" if price_info.get('daily_change_percent', 0) >= 0 else f"{price_info.get('daily_change_percent', 0.0):.2f}%",
                        "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "决策理由": "创业板股票已被排除"
                    }
            
            # 价格过滤检查（可选）
            enable_price_limits = self.config_manager.get('analysis_settings.filters.enable_price_limits', False)
            if enable_price_limits:
                current_price = price_info.get("current_price", 0.0)
                if (price_limit_min and current_price < price_limit_min) or (price_limit_max and current_price > price_limit_max):
                    price_range = ""
                    if price_limit_min and price_limit_max:
                        price_range = f"{price_limit_min}元到{price_limit_max}元"
                    elif price_limit_min:
                        price_range = f">= {price_limit_min}元"
                    elif price_limit_max:
                        price_range = f"<= {price_limit_max}元"
                    self.logger.info(f"股票价格{current_price:.2f}不在限制范围{price_range}内，跳过分析: {name}")
                    return {
                        "股票代码": symbol,
                        "股票名称": name,
                        "操作建议": "跳过",
                        "信心度": "0%",
                        "风险等级": "未知",
                        "当前价格": f"{current_price:.2f}元",
                        "当日最高": f"{price_info.get('daily_high', 0.0):.2f}元",
                        "当日最低": f"{price_info.get('daily_low', 0.0):.2f}元",
                        "当日涨跌": f"+{price_info.get('daily_change_percent', 0.0):.2f}%" if price_info.get('daily_change_percent', 0) >= 0 else f"{price_info.get('daily_change_percent', 0.0):.2f}%",
                        "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "决策理由": f"价格{current_price:.2f}元不在限制范围{price_range}内"
                    }
            
            # 获取缓存数据分析的轻量级组件（避免重复初始化数据源）
            components = self._get_cached_analysis_components()
            risk_manager = components['risk_manager']
            portfolio_manager = components['portfolio_manager']

            # AI因子分析
            analyses = []

            # 准备分析师输入信息
            analyst_inputs = {
                "symbol": symbol,
                "data_shape": data.shape if data is not None else "N/A",
                "data_date_range": f"{data.index[0].strftime('%Y-%m-%d')} 到 {data.index[-1].strftime('%Y-%m-%d')}" if data is not None and not data.empty else "N/A",
                "info_keys": list(info.keys()) if info else [],
                "indicators_keys": list(indicators.keys()) if indicators else [],
                "current_price": price_info.get("current_price", 0.0),
                "analysis_timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # AI因子分析
            if self.ai_factor_enabled and self.factor_manager:
                try:
                    ai_factor_analysis = self._ai_factor_analysis(symbol, data, indicators)
                    if ai_factor_analysis:
                        ai_factor_analysis["analyst_inputs"] = analyst_inputs.copy()
                        analyses.append(ai_factor_analysis)
                        self.logger.info(f"AI因子分析完成: {symbol}")
                except Exception as e:
                    self.logger.error(f"AI因子分析失败 {symbol}: {e}")
            
            # 风险评估
            risk_assessment = risk_manager.assess_risk(
                data=data,
                indicators=indicators,
                symbol=symbol,
                analyses=analyses
            )

            # 最终决策 (应用信号过滤)
            analysis_status["status"] = "making_decision"
            self.logger.info(f"🔍 [缓存分析] 开始最终决策: {symbol}, 分析师数量: {len(analyses)}")
            decision = portfolio_manager.make_decision(
                symbol, analyses, risk_assessment, price_info,
                data=data,  # 【新增】传入历史数据用于信号过滤
                position_info=None  # 正常预测无持仓信息
            )
            analysis_status["multi_round_debate_checked"] = True
            execution_time = time.time() - start_time
            self.logger.info(f"🔍 [缓存分析] 最终决策完成: {symbol}, 用时: {execution_time:.2f}秒")
            self.logger.info(f"🔍 [缓存分析] 决策对象中是否包含多轮辩论结果: {hasattr(decision, 'multi_round_debate_result') and decision.multi_round_debate_result is not None}")
            
            # 记录决策到记忆系统
            if self.enable_learning and self.memory_system:
                self.record_trading_decision(symbol, decision, analyses)

            # 使用输出管理器格式化结果
            result = self.output_manager.format_analysis_result(
                symbol=symbol,
                name=name,
                decision=decision,
                data=data,
                analyses=analyses,
                include_analyst_details=True
            )

            return result
            
        except Exception as e:
            self.logger.error(f"缓存分析股票失败 {symbol}: {e}")
            raise  # 重新抛出异常，让ThreadPoolAnalyzer处理
    
    def _analyze_stock_for_thread(self, symbol: str, name: str, price_limit_min: Optional[float] = None, price_limit_max: Optional[float] = None) -> Dict:
        """
        用于多线程分析的股票分析方法（废弃，不建议使用）
        
        这个方法保留是为了兼容性，但建议使用 batch_analyze_threaded 方法，
        它采用了更安全的数据获取和AI分析分离的策略。
        """
        try:
            # 使用线程安全的组件
            decision = self.analyze_stock(symbol, name, price_limit_min, price_limit_max, use_thread_safe=True)
            
            if decision.action in ["错误", "跳过"]:
                return {
                    "股票代码": symbol,
                    "股票名称": name,
                    "操作建议": decision.action,
                    "信心度": f"{decision.confidence:.2%}",
                    "风险等级": decision.risk_level,
                    "当前价格": f"{decision.current_price:.2f}元" if decision.current_price > 0 else "N/A",
                    "当日最高": f"{decision.daily_high:.2f}元" if decision.daily_high > 0 else "N/A",
                    "当日最低": f"{decision.daily_low:.2f}元" if decision.daily_low > 0 else "N/A",
                    "当日涨跌": f"{decision.daily_change_percent:+.2f}%" if decision.daily_change_percent != 0 else "0.00%",
                    "分析时间": decision.timestamp,
                    "决策理由": decision.reason
                }
            
            # 格式化涨跌幅显示
            change_display = ""
            if decision.daily_change_percent != 0:
                change_sign = "+" if decision.daily_change_percent > 0 else ""
                change_display = f"{change_sign}{decision.daily_change_percent:.2f}%"
            else:
                change_display = "0.00%"
            
            return {
                "股票代码": symbol,
                "股票名称": name,
                "操作建议": decision.action,
                "信心度": f"{decision.confidence:.2%}",
                "风险等级": decision.risk_level,
                "当前价格": f"{decision.current_price:.2f}元",
                "当日最高": f"{decision.daily_high:.2f}元",
                "当日最低": f"{decision.daily_low:.2f}元",
                "当日涨跌": change_display,
                "分析时间": decision.timestamp,
                "决策理由": decision.reason
            }
            
        except Exception as e:
            self.logger.error(f"线程分析股票失败 {name}({symbol}): {e}")
            return {
                "股票代码": symbol,
                "股票名称": name,
                "操作建议": "错误",
                "信心度": "0%",
                "风险等级": "未知",
                "当前价格": "N/A",
                "当日最高": "N/A",
                "当日最低": "N/A",
                "当日涨跌": "N/A",
                "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "决策理由": f"分析出错: {str(e)}"
            }


    def _collect_data_batch(self, stock_list: List[Tuple[str, str]]) -> Dict[str, Dict]:
        """批量收集股票数据(单线程,避免并发问题)"""
        data_cache = {}

        print(f"第1阶段: 批量收集 {len(stock_list)} 只股票的数据...")

        for i, (symbol, name) in enumerate(stock_list, 1):
            try:
                print(f"  收集进度: [{i}/{len(stock_list)}] {name}({symbol})")

                # 获取股票数据
                data, info, indicators, price_info = self.data_provider.get_stock_data(symbol)

                if data is not None and not data.empty:
                    data_cache[symbol] = {
                        'success': True,
                        'data': data,
                        'info': info,
                        'indicators': indicators,
                        'price_info': price_info,
                        'name': name
                    }
                    print(f"    {name} 数据收集成功")
                else:
                    data_cache[symbol] = {
                        'success': False,
                        'error': '数据为空或获取失败',
                        'name': name
                    }
                    print(f"    {name} 数据收集失败")

                # 添加小延迟避免请求过快
                time.sleep(0.2)

            except Exception as e:
                print(f"    {name} 数据收集异常: {e}")
                data_cache[symbol] = {
                    'success': False,
                    'error': str(e),
                    'name': name
                }

        successful_count = sum(1 for v in data_cache.values() if v.get('success'))
        print(f"数据收集完成: {successful_count}/{len(stock_list)} 只股票成功")

        return data_cache

    def batch_analyze_threaded(self, stock_list: List[Tuple[str, str]], price_limit_min: float = None, price_limit_max: float = None,
                              show_progress: bool = True) -> List[Dict]:
        """多线程批量分析股票（推荐使用）- 数据获取和AI分析分离版本"""
        if not stock_list:
            return []
        
        start_time = time.time()
        print(f"开始多线程批量分析 {len(stock_list)} 只股票...")
        if price_limit_min or price_limit_max:
            price_range = ""
            if price_limit_min and price_limit_max:
                price_range = f"{price_limit_min}元到{price_limit_max}元"
            elif price_limit_min:
                price_range = f">= {price_limit_min}元"
            elif price_limit_max:
                price_range = f"<= {price_limit_max}元"
            print(f"价格过滤条件: 只分析价格 {price_range} 的股票")
        
        try:
            # 阶段1: 单线程批量收集数据（避免并发问题）
            data_cache = self._collect_data_batch(stock_list)
            
            # 阶段2: AI分析（使用缓存数据，多线程）
            print(f"\n第2阶段: 多线程AI分析（{self.max_workers} 个线程）...")

            # 使用多线程池进行AI分析
            results = []
            completed_count = 0

            # 创建分析任务
            analysis_tasks = []
            for symbol, name in stock_list:
                analysis_tasks.append((symbol, name, price_limit_min, price_limit_max, data_cache))

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有分析任务
                future_to_task = {
                    executor.submit(
                        self._analyze_stock_with_cache,
                        task[0], task[1], task[2], task[3], task[4]
                    ): task
                    for task in analysis_tasks
                }

                # 处理完成的任务
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    symbol, name = task[0], task[1]
                    completed_count += 1

                    if show_progress:
                        self._progress_callback(completed_count-1, len(stock_list), name)

                    try:
                        result = future.result()

                        # 【新增】立即打印单只股票的分析结果,不用等到全部完成
                        action = result.get("操作建议", "未知")
                        confidence = result.get("信心度", "N/A")
                        price = result.get("当前价格", "N/A")
                        change = result.get("当日涨跌", "N/A")

                        # 根据操作建议使用不同的emoji
                        action_emoji = {"买入": "📈", "卖出": "📉", "持有": "➡️", "跳过": "⏭️", "错误": "❌"}
                        emoji = action_emoji.get(action, "❓")

                        print(f"\n{emoji} [{completed_count}/{len(stock_list)}] {name}({symbol}) 分析完成:")
                        print(f"    操作: {action} | 信心度: {confidence} | 价格: {price} | 涨跌: {change}")

                        # 可选:打印决策理由的前50个字符
                        reason = result.get("决策理由", "")
                        if reason and len(reason) > 0:
                            reason_preview = reason[:50] + "..." if len(reason) > 50 else reason
                            print(f"    理由: {reason_preview}")

                        # 模拟AnalysisResult结构
                        class MockResult:
                            def __init__(self, result, task_info):
                                self.result = result
                                self.task = task_info

                        class MockTask:
                            def __init__(self, symbol, name):
                                self.symbol = symbol
                                self.name = name

                        mock_task = MockTask(symbol, name)
                        mock_result = MockResult(result, mock_task)
                        results.append(mock_result)

                    except Exception as e:
                        self.logger.error(f"多线程分析股票失败 {symbol}: {e}")
                        # 创建错误结果
                        error_result = {
                            "股票代码": symbol,
                            "股票名称": name,
                            "操作建议": "错误",
                            "信心度": "0%",
                            "风险等级": "未知",
                            "当前价格": "N/A",
                            "当日最高": "N/A",
                            "当日最低": "N/A",
                            "当日涨跌": "N/A",
                            "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "决策理由": f"多线程分析错误: {str(e)}"
                        }
                        mock_task = MockTask(symbol, name)
                        mock_result = MockResult(error_result, mock_task)
                        results.append(mock_result)
            
            # 转换结果格式
            formatted_results = []
            for result in results:
                if isinstance(result.result, dict):
                    formatted_results.append(result.result)
                else:
                    # 处理异常情况
                    data_info = data_cache.get(result.task.symbol, {})
                    formatted_results.append({
                        "股票代码": result.task.symbol,
                        "股票名称": data_info.get('name', result.task.name),
                        "操作建议": "错误",
                        "信心度": "0%",
                        "风险等级": "未知",
                        "当前价格": "N/A",
                        "当日最高": "N/A",
                        "当日最低": "N/A",
                        "当日涨跌": "N/A",
                        "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "决策理由": f"数据获取失败: {data_info.get('error', '未知错误')}"
                    })
            
            elapsed_time = time.time() - start_time
            successful_analyses = sum(1 for r in formatted_results if r["操作建议"] not in ["错误", "跳过"])
            
            print(f"\n批量分析完成!")
            print(f"成功分析: {successful_analyses}/{len(stock_list)} 只股票")
            print(f"⏱️ 总耗时: {elapsed_time:.2f}秒")
            print(f"平均速度: {len(stock_list)/elapsed_time:.2f} 只/秒")
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"多线程批量分析失败: {e}")
            return []
    
    def batch_analyze(self, stock_list: List[Tuple[str, str]], price_limit_min: float = None, price_limit_max: float = None) -> List[Dict]:
        """单线程批量分析股票（简单但较慢）"""
        total_stocks = len(stock_list)
        
        # 提示用户可以使用多线程版本
        if total_stocks > 10:
            print(f"💡 提示: 您正在分析 {total_stocks} 只股票，建议使用多线程版本 batch_analyze_threaded() 以获得更好的性能")
            print(f"    多线程版本可提供约 {self.max_workers}x 的性能提升")
            print()
        
        results = []
        skipped_count = 0
        analyzed_count = 0
        
        start_time = time.time()
        print(f"开始单线程批量分析 {total_stocks} 只股票...")
        if price_limit_min or price_limit_max:
            price_range = ""
            if price_limit_min and price_limit_max:
                price_range = f"{price_limit_min}元到{price_limit_max}元"
            elif price_limit_min:
                price_range = f">= {price_limit_min}元"
            elif price_limit_max:
                price_range = f"<= {price_limit_max}元"
            print(f"价格过滤条件: 只分析价格 {price_range} 的股票")
        
        for i, (symbol, name) in enumerate(stock_list, 1):
            try:
                print(f"进度: [{i}/{total_stocks}] 正在分析 {name}({symbol})...")
                decision = self.analyze_stock(symbol, name, price_limit_min, price_limit_max)
                
                if decision.action == "跳过":
                    skipped_count += 1
                else:
                    analyzed_count += 1
                
                # 格式化涨跌幅显示
                change_display = ""
                if decision.daily_change_percent != 0:
                    change_sign = "+" if decision.daily_change_percent > 0 else ""
                    change_display = f"{change_sign}{decision.daily_change_percent:.2f}%"
                else:
                    change_display = "0.00%"
                
                result = {
                    "股票代码": symbol,
                    "股票名称": name,
                    "操作建议": decision.action,
                    "信心度": f"{decision.confidence:.2%}",
                    "风险等级": decision.risk_level,
                    "当前价格": f"{decision.current_price:.2f}元",
                    "当日最高": f"{decision.daily_high:.2f}元",
                    "当日最低": f"{decision.daily_low:.2f}元",
                    "当日涨跌": change_display,
                    "分析时间": decision.timestamp,
                    "决策理由": decision.reason
                }
                
                # 添加目标价格信息（仅在有有效数据时）
                if hasattr(decision, 'target_price_medium') and decision.target_price_medium > 0:
                    price_targets = {}
                    if decision.target_price_short > 0:
                        price_targets["短期目标(0-14天)"] = f"{decision.target_price_short:.2f}元"
                    if decision.target_price_medium > 0:
                        price_targets["中期目标(15-30天)"] = f"{decision.target_price_medium:.2f}元"
                    if decision.target_price_long > 0:
                        price_targets["长期目标(90天)"] = f"{decision.target_price_long:.2f}元"
                    if decision.upside_potential != 0:
                        price_targets["上涨空间"] = f"{decision.upside_potential:.2%}"
                    if decision.price_range_low > 0 and decision.price_range_high > 0:
                        price_targets["价格区间"] = f"{decision.price_range_low:.2f}-{decision.price_range_high:.2f}元"

                    result.update(price_targets)
                
                results.append(result)
            except Exception as e:
                self.logger.error(f"分析股票 {name}({symbol}) 时出错: {e}")
                results.append({
                    "股票代码": symbol,
                    "股票名称": name,
                    "操作建议": "错误",
                    "信心度": "0%",
                    "风险等级": "未知",
                    "当前价格": "N/A",
                    "当日最高": "N/A",
                    "当日最低": "N/A",
                    "当日涨跌": "N/A",
                    "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "决策理由": f"分析出错: {str(e)}"
                })
        
        elapsed_time = time.time() - start_time
        print(f"\n单线程分析完成: 成功 {analyzed_count} 只, 跳过 {skipped_count} 只, 总耗时 {elapsed_time:.2f}秒")
        
        return results
    
    def print_analysis_results(self, results: List[Dict]):
        """打印分析结果"""
        self.output_manager.print_analysis_results(results)

        # 保存结果
        self.save_results(results)

    def save_results(self, results: List[Dict]):
        """保存分析结果到时间戳文件夹"""
        self.output_manager.save_results(results)

    def _ai_factor_analysis(self, symbol: str, data: pd.DataFrame, indicators: Dict) -> Optional[Dict]:
        """
        AI因子分析
        
        Args:
            symbol: 股票代码
            data: 股票数据
            indicators: 技术指标数据
            
        Returns:
            AI因子分析结果
        """
        try:
            if not self.ai_factor_enabled or not self.factor_manager:
                return None
                
            # 准备因子计算所需的数据格式
            # 因子期望的数据格式是 Dict[str, pd.DataFrame]，其中键是依赖名称
            symbol_data = {
                'price': data[['Open', 'High', 'Low', 'Close']].copy(),  # 价格数据
                'volume': data[['Volume']].copy()  # 成交量数据
            }
            
            # 【新方法】使用加权因子信号（自动IC评估）
            # 这个方法会：
            # 1. 计算所有因子
            # 2. 自动记录因子值（用于IC计算）
            # 3. 应用IC评估后的权重
            # 4. 每50次分析或每7天自动触发IC评估和权重调整
            weighted_signal = self.factor_manager.calculate_weighted_signal(symbol, symbol_data)

            # 同时获取详细因子值（用于显示）
            factors = self.factor_manager.calculate_all_factors(symbol, symbol_data)

            if not factors:
                return None

            # 分析因子结果并给出投资建议
            factor_scores = []
            factor_details = {}

            for factor_name, factor_value in factors.items():
                score = factor_value.value

                # 过滤 NaN 值，只添加有效分数
                if not np.isnan(score) and np.isfinite(score):
                    factor_scores.append(score)

                # 获取因子描述和权重信息（从因子管理器中获取）
                factor_description = ''
                factor_weight = 1.0
                is_disabled = False

                if self.factor_manager and factor_name in self.factor_manager.factors:
                    factor_description = self.factor_manager.factors[factor_name].description

                    # 获取IC评估后的权重
                    if self.factor_manager.enable_auto_evaluation:
                        factor_weight = self.factor_manager.factor_weights.get(factor_name, 1.0)
                        is_disabled = factor_name in self.factor_manager.disabled_factors

                factor_details[factor_name] = {
                    'value': score if not np.isnan(score) else None,
                    'timestamp': factor_value.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'description': factor_description,
                    'weight': factor_weight,  # IC评估后的权重
                    'disabled': is_disabled    # 是否被禁用
                }

            # 【改进】使用加权信号而非简单平均
            if factor_scores and len(factor_scores) > 0:
                # 使用IC评估后的加权信号
                avg_score = weighted_signal
                std_score = np.std(factor_scores) if len(factor_scores) > 1 else 0
                
                # 基于因子评分给出建议
                if avg_score > 0.6:
                    recommendation = "买入"
                    confidence = min(0.9, 0.5 + avg_score * 0.4)
                elif avg_score > 0.3:
                    recommendation = "持有"
                    confidence = min(0.7, 0.3 + avg_score * 0.4)
                elif avg_score > -0.3:
                    recommendation = "持有"
                    confidence = min(0.6, 0.2 + abs(avg_score) * 0.4)
                else:
                    recommendation = "卖出"
                    confidence = min(0.8, 0.4 + abs(avg_score) * 0.4)

                reasoning = [
                    f"AI因子加权评分: {avg_score:.4f} (已应用IC评估权重)",
                    f"因子评分标准差: {std_score:.4f}",
                    f"有效因子数量: {len(factor_scores)}/{len(factors)}"
                ]

                # 【新增】显示IC评估状态
                if self.factor_manager.enable_auto_evaluation:
                    reasoning.append(f"已分析次数: {self.factor_manager.analysis_count} 次")
                    if self.factor_manager.disabled_factors:
                        reasoning.append(f"已禁用因子: {len(self.factor_manager.disabled_factors)} 个")

                # 添加主要因子的贡献说明（只包含有效且启用的因子）
                sorted_factors = sorted(
                    [(name, info) for name, info in factor_details.items()
                     if info['value'] is not None and not info.get('disabled', False)],
                    key=lambda x: abs(x[1]['value']) * x[1].get('weight', 1.0),  # 按加权贡献排序
                    reverse=True
                )

                for i, (factor_name, factor_info) in enumerate(sorted_factors[:3]):
                    contribution = "正面" if factor_info['value'] > 0 else "负面"
                    weight = factor_info.get('weight', 1.0)
                    weight_str = f", 权重={weight:.2f}" if self.factor_manager.enable_auto_evaluation else ""
                    reasoning.append(f"{factor_name}: {factor_info['value']:.4f} ({contribution}贡献{weight_str})")
                
                return {
                    "analyst_type": "AI因子分析",
                    "recommendation": recommendation,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "factor_details": factor_details,
                    "factor_summary": {
                        "avg_score": avg_score,
                        "std_score": std_score,
                        "factor_count": len(factor_scores)
                    },
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

            # 如果没有有效因子，返回降级建议
            else:
                self.logger.warning(f"股票 {symbol} 所有AI因子计算结果无效，返回保守建议")
                return {
                    "analyst_type": "AI因子分析",
                    "recommendation": "持有",
                    "confidence": 0.3,
                    "reasoning": [
                        "AI因子综合评分: 数据不足",
                        "因子评分标准差: 数据不足",
                        f"有效因子数量: 0/{len(factors)}",
                        "建议: 数据不足，保守持有观望"
                    ],
                    "factor_details": factor_details,
                    "factor_summary": {
                        "avg_score": None,
                        "std_score": None,
                        "factor_count": 0
                    },
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

        except Exception as e:
            self.logger.error(f"AI因子分析计算失败 {symbol}: {e}")
            return None

    def _is_chinext_stock(self, symbol: str) -> bool:
        """判断是否为创业板股票
        
        创业板股票代码规则：
        - 深交所创业板：300xxx（主要）
        - 北交所：430xxx, 830xxx（新三板转板）
        """
        if not symbol or len(symbol) < 6:
            return False
            
        # 提取数字部分
        code = symbol.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
        
        # 创业板：300开头的6位数字
        if code.startswith('300') and len(code) == 6 and code.isdigit():
            return True
        
        # 北交所部分股票也可能被归类为创业板类型
        if (code.startswith('430') or code.startswith('830')) and len(code) == 6 and code.isdigit():
            return True

        return False


def main():
    """主函数"""
    # 设置控制台输出编码
    import sys
    import argparse
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='A股量化交易系统')
    parser.add_argument('--mode', type=str, default='select',
                       choices=['select', 'hold', 'both', 'backtest'],
                       help='运行模式: select=选股分析, hold=持仓分析, both=两者都执行, backtest=历史回测')
    parser.add_argument('--output-dir', type=str, default=None,
                       help='输出目录路径，如果不指定则自动生成')
    parser.add_argument('--start-date', type=str, default=None,
                       help='回测开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None,
                       help='回测结束日期 (YYYY-MM-DD)')
    parser.add_argument('--months', type=int, default=3,
                       help='回测向前月数（当未指定日期时使用）')
    args = parser.parse_args()

    # 总体耗时统计开始
    total_start_time = time.time()
    main_logger = logging.getLogger("AShareTradingSystem")
    main_logger.info("🚀 ================ A股量化交易系统启动 ================")
    main_logger.info(f"📋 运行模式: {args.mode}")

    # 根据模式设置输出目录
    if args.output_dir:
        # 使用指定的输出目录（定时器传递的路径）
        output_dir = args.output_dir
        main_logger.info(f"📁 使用指定的输出目录: {output_dir}")
    else:
        # 自动生成输出目录（回测使用独立目录）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if args.mode == 'backtest':
            output_dir = os.path.join("backtest_results", timestamp)
        else:
            output_dir = os.path.join("outputs", timestamp)
        main_logger.info(f"📁 自动生成输出目录: {output_dir}")

    os.makedirs(output_dir, exist_ok=True)
    main_logger.info(f"📁 最终输出目录: {output_dir}")

    print("启动基于TradingAgents的A股量化交易系统")
    print(f"运行模式: {args.mode}")
    print(f"输出目录: {output_dir}")
    print("="*60)
    
    # 检查依赖
    try:
        import yfinance
        import pandas
        import numpy
        print("依赖检查通过")
    except ImportError as e:
        print(f"缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    
    # 第一阶段：系统初始化
    phase1_start_time = time.time()
    main_logger.info("📋 第一阶段：系统初始化开始...")

    try:
        system = AShareTradingAgentsSystem()
        # 设置输出目录（统一输出路径）
        system.output_manager.output_dir = output_dir
        main_logger.info(f"📁 系统输出目录设置为: {output_dir}")

  
        phase1_init_time = time.time() - phase1_start_time
        main_logger.info(f"✅ 系统初始化完成，耗时: {phase1_init_time:.2f}秒")
    except Exception as e:
        print(f"系统初始化失败: {e}")
        main_logger.error(f"❌ 系统初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========== 回测模式：历史数据回测 ==========
    if args.mode == 'backtest':
        print("\n" + "="*60)
        print("历史回测模式：对历史数据进行逐日分析和模拟交易")
        print("="*60)

        from src.backtest.historical_backtest_runner import HistoricalBacktestRunner

        # 创建历史回测运行器
        backtest_runner = HistoricalBacktestRunner(system)

        # 显示回测配置
        if args.start_date and args.end_date:
            print(f"回测时间范围: {args.start_date} 至 {args.end_date}")
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30 * args.months)).strftime("%Y-%m-%d")
            print(f"回测时间范围: {start_date} 至 {end_date} (最近{args.months}个月)")

        print("股票池: 使用选股系统自动选择（复用 config/dynamic_stock.json 或重新选股）")
        print("\n开始历史回测...")

        # 运行历史回测
        backtest_results = backtest_runner.run_historical_backtest(
            symbols=None,  # 使用选股系统
            start_date=args.start_date,
            end_date=args.end_date,
            months_back=args.months
        )

        # 打印回测结果
        if 'error' in backtest_results:
            print(f"\n❌ 回测失败: {backtest_results['error']}")
        else:
            print("\n" + "="*60)
            print("回测结果摘要")
            print("="*60)

            config_info = backtest_results.get('backtest_config', {})
            print(f"回测时间范围: {config_info.get('start_date')} 至 {config_info.get('end_date')}")
            print(f"回测股票数量: {config_info.get('stock_count')} 只")
            print(f"交易日数量: {config_info.get('trading_days')} 天")
            print(f"生成决策数: {config_info.get('decision_count')} 条")
            print(f"初始资金: ¥{config_info.get('initial_capital', 0):,.0f}")

            print(f"\n收益指标:")
            print(f"  总收益率: {backtest_results.get('total_return', 0):.2%}")
            print(f"  年化收益率: {backtest_results.get('annualized_return', 0):.2%}")
            print(f"  最终资金: ¥{backtest_results.get('final_capital', 0):,.2f}")
            print(f"  盈亏金额: ¥{backtest_results.get('profit', 0):,.2f}")

            print(f"\n风险指标:")
            print(f"  年化波动率: {backtest_results.get('volatility', 0):.2%}")
            print(f"  夏普比率: {backtest_results.get('sharpe_ratio', 0):.2f}")
            print(f"  最大回撤: {backtest_results.get('max_drawdown', 0):.2%}")

            print(f"\n交易统计:")
            print(f"  总交易次数: {backtest_results.get('total_trades', 0)} 笔")
            print(f"  买入次数: {backtest_results.get('buy_trades', 0)} 笔")
            print(f"  卖出次数: {backtest_results.get('sell_trades', 0)} 笔")
            print(f"  胜率: {backtest_results.get('win_rate', 0):.2%}")
            print(f"  平均持有天数: {backtest_results.get('avg_holding_days', 0):.1f} 天")

            # 保存回测结果
            backtest_output_file = os.path.join(output_dir, "backtest_results.json")
            import json
            with open(backtest_output_file, 'w', encoding='utf-8') as f:
                # 简化结果（移除大数组和DataFrame）
                simplified_results = {
                    k: v for k, v in backtest_results.items()
                    if k not in ['daily_returns', 'portfolio_values', 'trade_history', 'historical_data']
                }
                simplified_results['trade_summary'] = {
                    'total_trades': len(backtest_results.get('trade_history', [])),
                    'first_5_trades': backtest_results.get('trade_history', [])[:5]
                }
                json.dump(simplified_results, f, ensure_ascii=False, indent=2)

            print(f"\n回测结果已保存至: {backtest_output_file}")

            # 保存详细交易记录（添加股票名称）
            trade_history = backtest_results.get('trade_history', [])
            symbol_to_name = backtest_results.get('symbol_to_name', {})

            # 为每条交易记录添加股票名称
            enhanced_trade_history = []
            for trade in trade_history:
                enhanced_trade = trade.copy()
                symbol = trade.get('symbol', '')
                enhanced_trade['name'] = symbol_to_name.get(symbol, symbol)
                enhanced_trade_history.append(enhanced_trade)

            trade_history_file = os.path.join(output_dir, "backtest_trade_history.json")
            with open(trade_history_file, 'w', encoding='utf-8') as f:
                json.dump(enhanced_trade_history, f, ensure_ascii=False, indent=2)
            print(f"详细交易记录已保存至: {trade_history_file}")

            # 生成Markdown报告
            try:
                from src.backtest.backtest_report_generator import generate_backtest_markdown
                markdown_file = os.path.join(output_dir, "backtest_result.md")
                generate_backtest_markdown(backtest_results, markdown_file)
                print(f"Markdown报告已保存至: {markdown_file}")
            except Exception as e:
                print(f"⚠️ Markdown报告生成失败: {e}")

            # 生成K线图
            try:
                from src.backtest.backtest_chart_generator import generate_backtest_charts
                print("\n正在生成K线图...")
                historical_data = backtest_results.get('historical_data', {})
                if historical_data:
                    chart_files = generate_backtest_charts(backtest_results, historical_data, output_dir)
                    if chart_files:
                        print(f"✅ K线图生成完成，共 {len(chart_files)} 个文件")
                        print(f"K线图保存在: {os.path.join(output_dir, 'charts')}")
                    else:
                        print("⚠️ 没有生成K线图")
                else:
                    print("⚠️ 没有历史数据，跳过K线图生成")
            except Exception as e:
                print(f"⚠️ K线图生成失败: {e}")
                import traceback
                traceback.print_exc()

        print("\n回测模式执行完成")
        return

    # ========== 根据模式确定股票列表来源 ==========
    # 获取通用配置（所有模式都需要）
    from config.config_manager import get_config
    config = get_config()

    if args.mode == 'hold':
        # hold 模式：只加载持仓股票
        print("\n" + "="*60)
        print("持仓模式：仅分析持仓股票")
        print("="*60)

        try:
            import json
            hold_config_path = os.path.join("config", "hold_stock.json")
            if os.path.exists(hold_config_path):
                with open(hold_config_path, 'r', encoding='utf-8') as f:
                    hold_config = json.load(f)
                    hold_stocks = hold_config.get('hold_stocks', [])

                # 转换为 (symbol, name) 元组列表，只包含 buy_flag=True 的股票
                stock_list = [(stock['symbol'], stock['name']) for stock in hold_stocks if stock.get('buy_flag', True)]
                total_hold = len(hold_stocks)
                actual_bought = len(stock_list)
                watch_only = total_hold - actual_bought
                print(f"✅ 加载 {actual_bought} 只实际持仓股票 (观察中: {watch_only}只)")
                main_logger.info(f"📊 持仓模式加载{actual_bought}只实际持仓股票, {watch_only}只观察股票被过滤")
            else:
                print(f"❌ 未找到持仓配置文件: {hold_config_path}")
                main_logger.error(f"未找到持仓配置文件: {hold_config_path}")
                stock_list = []
                metadata = {'selection_method': 'hold', 'sources': {}, 'selection_time': 0.0}
        except Exception as e:
            print(f"❌ 读取持仓股票失败: {e}")
            main_logger.error(f"读取持仓股票失败: {e}")
            stock_list = []
            metadata = {'selection_method': 'hold', 'sources': {}, 'selection_time': 0.0}

    elif args.mode in ['select', 'both']:
        # select/both 模式：使用动态选股（both 模式会自动包含持仓股票）
        stock_selection_start = time.time()  # 开始股票选择计时

        if args.mode == 'both':
            print("\n" + "="*60)
            print("全分析模式：动态选股 + 持仓分析")
            print("="*60)

        try:
            from src.stock.stock_selection_manager import StockSelectionManager
            print("正在使用股票选择管理器...")

            # 初始化股票选择管理器
            stock_manager = StockSelectionManager(config)

            # 获取选股结果和元数据
            stock_list, metadata = stock_manager.get_selected_stocks()

            stock_selection_time = time.time() - stock_selection_start
            main_logger.info(f"✅ 股票选择完成，耗时: {stock_selection_time:.2f}秒")

            # 显示选股信息
            selection_method = metadata.get('selection_method', 'unknown')
            print(f"选股完成，方法: {selection_method}")
            print(f"共选择 {len(stock_list)} 只股票")
            main_logger.info(f"📊 选股结果: 方法={selection_method}, 数量={len(stock_list)}")

            # 显示来源分布（如果有）
            sources = metadata.get('sources', {})
            if sources:
                print("股票来源分布:")
                source_info = []
                for source, count in sources.items():
                    if count > 0:
                        print(f"  - {source}: {count} 只")
                        source_info.append(f"{source}={count}")
                main_logger.info(f"📊 股票来源分布: {', '.join(source_info)}")

            # both 模式：持仓股票已经包含在 stock_list 中
            if args.mode == 'both':
                print(f"📊 注意: 持仓股票已自动包含在选股列表中")
                main_logger.info("📊 both模式：持仓股票已包含在选股列表中")

            # 前日涨幅过滤
            filter_config = config.get('analysis_settings.filters.previous_day_change', {})
            if filter_config.get('enabled', False):
                try:
                    from src.filters.previous_day_filter import PreviousDayChangeFilter

                    original_count = len(stock_list)
                    print(f"\n正在过滤前日大涨股票（阈值: {filter_config.get('max_increase_percent', 9.0)}%）...")
                    main_logger.info(f"🔍 启动前日涨幅过滤器")

                    # 构建持仓股票列表（用于过滤器例外处理）
                    hold_stock_symbols = []
                    try:
                        import json
                        hold_config_path = os.path.join("config", "hold_stock.json")
                        if os.path.exists(hold_config_path):
                            with open(hold_config_path, 'r', encoding='utf-8') as f:
                                hold_config = json.load(f)
                                hold_stock_symbols = [stock['symbol'] for stock in hold_config.get('hold_stocks', []) if stock.get('buy_flag', True)]
                                main_logger.info(f"📊 过滤器例外股票: {len(hold_stock_symbols)}只实际持仓")
                    except Exception as e:
                        main_logger.warning(f"读取持仓配置失败: {e}")

                    prev_day_filter = PreviousDayChangeFilter(config, system.data_provider, hold_stock_symbols)
                    stock_list = prev_day_filter.filter_stocks(stock_list)

                    filtered_count = original_count - len(stock_list)
                    print(f"过滤完成: 保留 {len(stock_list)} 只，过滤 {filtered_count} 只")
                    main_logger.info(f"✅ 过滤完成: 保留{len(stock_list)}只，过滤{filtered_count}只")
                except Exception as filter_error:
                    print(f"⚠️ 前日涨幅过滤失败: {filter_error}，跳过过滤")
                    main_logger.warning(f"前日涨幅过滤失败: {filter_error}")
        except Exception as e:
            print(f"动态股票选择失败: {e}")
            print("使用传统配置文件股票列表...")
            try:
                from src.stock import get_all_stocks
                stock_list = get_all_stocks()[:20]  # 限制数量
            except ImportError:
                print("无法导入股票列表，使用默认列表")
                stock_list = []

    # 第一阶段总结（系统初始化 + 股票选择）
    phase1_total_time = time.time() - phase1_start_time
    main_logger.info(f"✅ 第一阶段完成（系统初始化 + 股票选择），总耗时: {phase1_total_time:.2f}秒")

    # 第二阶段：股票分析（所有模式统一执行）
    phase2_start_time = time.time()
    main_logger.info("📈 第二阶段：股票分析开始...")

    # 从配置获取价格限制（如果启用的话）
    config = get_config()
    price_limit_min = config.get_price_limit_min()
    price_limit_max = config.get_price_limit_max()
    enable_price_limits = config.get('analysis_settings.filters.enable_price_limits', False)

    print(f"\n准备分析 {len(stock_list)} 只A股股票...")
    main_logger.info(f"📊 准备分析{len(stock_list)}只股票")

    if enable_price_limits:
        print(f"价格筛选条件: 只分析价格{price_limit_min}元到{price_limit_max}元的股票")
        main_logger.info(f"💰 价格筛选: {price_limit_min}元-{price_limit_max}元")
    else:
        print("价格筛选: 已禁用，将分析所有价格区间的股票")
        main_logger.info("💰 价格筛选: 已禁用")

    print("正在获取数据和分析，请稍候...\n")

    # 执行批量分析（使用多线程版本）
    results = []
    holdings_summary = None  # 用于存储持仓概览

    try:
        results = system.batch_analyze_threaded(stock_list, price_limit_min, price_limit_max)

        phase2_analysis_time = time.time() - phase2_start_time
        main_logger.info(f"✅ 股票分析完成，耗时: {phase2_analysis_time:.2f}秒")
        main_logger.info(f"📊 分析结果: 成功分析{len(results)}只股票")

        # 打印分析结果
        system.print_analysis_results(results)

        # ========== 持仓分析（hold/both 模式）==========
        if args.mode in ['hold', 'both']:
            print("\n" + "="*60)
            print("🔍 开始持仓股票分析")
            print("="*60)
            main_logger.info("🔍 ================ 持仓分析开始 ================")

            hold_start_time = time.time()

            try:
                # 初始化持仓分析流程（传入输出目录）
                from src.process.hold_stock_process import HoldStockProcess
                hold_process = HoldStockProcess(system, config, output_dir=output_dir)

                # 执行完整流程（使用已有的分析结果复用数据）
                hold_result = hold_process.execute_full_process(analysis_results=results)

                hold_elapsed = time.time() - hold_start_time
                main_logger.info(f"✅ 持仓分析完成，耗时: {hold_elapsed:.2f}秒")

                if hold_result.get('success'):
                    print(f"\n✅ 持仓分析完成！")
                    print(f"分析耗时: {hold_elapsed:.2f}秒")
                    print(f"CSV文件: {hold_result.get('csv_file', 'N/A')}")
                    print(f"💡 已复用选股分析结果，节省了AI调用")

                    # 保存持仓概览用于 README 生成
                    holdings_summary = hold_result.get('summary')
                else:
                    print(f"\n❌ 持仓分析失败: {hold_result.get('error', '未知错误')}")
                    main_logger.error(f"❌ 持仓分析失败: {hold_result.get('error', '未知错误')}")

            except Exception as e:
                print(f"\n❌ 持仓分析出错: {e}")
                main_logger.error(f"❌ 持仓分析出错: {e}")
                import traceback
                traceback.print_exc()

            main_logger.info("🏁 ================ 持仓分析完成 ================")

        # 保存结果（传入持仓概览以生成综合 README）
        system.output_manager.save_results(results, holdings_summary=holdings_summary)

        # 分析完成后进行历史学习
        if system.enable_learning:
            print("\n正在从历史记录中学习...")
            learning_result = system.learn_from_history()
            if learning_result.get("success"):
                print("历史学习完成，已更新分析师权重")
            else:
                print(f"历史学习失败: {learning_result.get('error', '未知错误')}")

        print("\n分析完成！您可以查看输出的CSV和JSON文件获取详细结果。")

    except Exception as e:
        print(f"系统执行出错: {e}")
        main_logger.error(f"❌ 系统执行出错: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 总体耗时统计
        total_execution_time = time.time() - total_start_time
        main_logger.info(f"🏁 ================ 系统执行完成 ================")
        main_logger.info(f"⏱️  总耗时: {total_execution_time:.2f}秒 ({total_execution_time/60:.1f}分钟)")
        if len(stock_list) > 0:
            main_logger.info(f"📊 效率统计: 平均每只股票 {total_execution_time/len(stock_list):.2f}秒")
        print(f"\n系统总耗时: {total_execution_time:.2f}秒")

if __name__ == "__main__":
    main()