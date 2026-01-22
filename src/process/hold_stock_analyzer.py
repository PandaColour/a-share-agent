# -*- coding: utf-8 -*-
"""
持仓分析器
负责分析持仓股票的收益、止损和操作建议
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import pandas as pd

logger = logging.getLogger(__name__)


class HoldStockAnalyzer:
    """持仓股票分析器"""

    def __init__(self, system=None, config=None):
        """
        初始化持仓分析器

        Args:
            system: A股TradingAgents系统实例
            config: 配置管理器实例
        """
        self.system = system
        self.config = config
        self.today = date.today()
        self.logger = logging.getLogger(__name__)

    def analyze_position(self, stock: Dict, existing_result: Dict = None) -> Dict:
        """
        分析单只持仓股票

        Args:
            stock: 股票信息字典
            existing_result: 已有的分析结果（可选），如果提供则复用数据

        Returns:
            完整的分析结果
        """
        try:
            symbol = stock['symbol']
            name = stock['name']
            cost = stock['cost']
            purchase_date = stock['purchase_date']

            self.logger.info(f"开始分析持仓股票: {name}({symbol})")

            # 1. 获取当前价格
            current_price, price_info = self._get_current_price(symbol)

            if current_price is None or current_price == 0:
                return self._create_error_analysis(stock, "无法获取当前价格")

            # 2. 计算持仓天数
            holding_days = self._calculate_holding_days(purchase_date)

            # 3. 计算收益
            profit_loss = current_price - cost
            profit_loss_rate = (profit_loss / cost) * 100  # 百分比

            # 4. 确定收益状态
            profit_status = self._determine_profit_status(profit_loss_rate)

            # 5. 计算止损价格和状态
            stop_loss_info = self._calculate_stop_loss(cost, holding_days, current_price)

            # 6. 获取系统分析建议（如果提供了existing_result则复用，否则调用系统）
            if existing_result:
                # 从选股分析结果中提取数据（使用中文字段名）
                recommendation = existing_result.get('操作建议', '持有')
                confidence_str = existing_result.get('信心度', '0%')  # 已经是 "60.20%" 格式
                reason = existing_result.get('决策理由', '')

                system_analysis = {
                    'recommendation': recommendation,
                    'confidence': confidence_str,  # 直接使用字符串格式
                    'reason': reason[:100] if reason else ''
                }
                self.logger.info(f"使用已有分析结果: {system_analysis['recommendation']} (信心度: {confidence_str})")
            else:
                system_analysis = self._get_system_analysis(symbol, name)

            # 7. 生成综合操作建议
            action_advice = self._generate_action_advice(
                profit_loss_rate,
                stop_loss_info,
                system_analysis,
                holding_days
            )

            # 8. 构建完整分析结果
            analysis_result = {
                # 基础信息
                "股票代码": symbol,
                "股票名称": name,
                "成本价": cost,
                "当前价格": current_price,
                "持仓天数": holding_days,
                "购买日期": purchase_date,

                # 收益分析
                "持仓收益": profit_loss,
                "持仓收益率": profit_loss_rate,
                "收益状态": profit_status,

                # 止损分析
                "止损规则": stop_loss_info['rule'],
                "止损价格": stop_loss_info['price'],
                "距离止损": stop_loss_info['distance'],
                "预警状态": stop_loss_info['warning_status'],

                # 系统分析
                "系统建议": system_analysis['recommendation'],
                "系统信心度": system_analysis['confidence'],
                "系统理由": system_analysis['reason'],

                # 综合建议
                "操作建议": action_advice['action'],
                "建议理由": action_advice['reasons'],
                "风险提示": action_advice['risk_warning'],
                "下一步行动": action_advice['next_action'],

                # 价格信息
                "当日最高": price_info.get('daily_high', 0),
                "当日最低": price_info.get('daily_low', 0),
                "当日涨跌": price_info.get('daily_change_percent', 0)
            }

            self.logger.info(f"完成分析: {name} - {action_advice['action']}")
            return analysis_result

        except Exception as e:
            self.logger.error(f"分析持仓股票失败 {stock.get('symbol', 'Unknown')}: {e}")
            return self._create_error_analysis(stock, str(e))

    def _get_current_price(self, symbol: str) -> Tuple[Optional[float], Dict]:
        """获取当前价格"""
        try:
            if not self.system:
                return None, {}

            data, info, indicators, price_info, intraday_data, _ = self.system.data_provider.get_stock_data(symbol)

            if data is None or data.empty:
                return None, {}

            current_price = price_info.get('current_price', 0.0)
            return current_price, price_info

        except Exception as e:
            self.logger.error(f"获取价格失败 {symbol}: {e}")
            return None, {}

    def _calculate_holding_days(self, purchase_date: str) -> int:
        """计算持仓天数"""
        try:
            if purchase_date == '未知':
                return 0
            purchase_dt = datetime.strptime(purchase_date, '%Y-%m-%d').date()
            return (self.today - purchase_dt).days
        except:
            return 0

    def _determine_profit_status(self, profit_rate: float) -> str:
        """确定收益状态"""
        if profit_rate > 0.1:
            return "盈利"
        elif profit_rate < -0.1:
            return "亏损"
        else:
            return "持平"

    def _calculate_stop_loss(self, cost: float, holding_days: int,
                            current_price: float) -> Dict:
        """
        计算止损价格和状态

        Args:
            cost: 成本价
            holding_days: 持仓天数
            current_price: 当前价格

        Returns:
            止损信息字典
        """
        # 购买当日不设止损
        if holding_days == 0:
            return {
                'rule': '购买当日-不设止损',
                'price': None,
                'distance': 'N/A',
                'warning_status': '正常',
                'warning_level': 0
            }

        # 观察期(1-3天): 临时止损-3%
        elif holding_days <= 3:
            stop_loss_price = cost * 0.97
            distance_pct = ((current_price - stop_loss_price) / stop_loss_price) * 100

            # 判断预警状态
            if current_price <= stop_loss_price:
                warning_status = '触发止损'
                warning_level = 3
            elif distance_pct <= 1:
                warning_status = '严重警告'
                warning_level = 2
            elif distance_pct <= 2:
                warning_status = '警告'
                warning_level = 1
            else:
                warning_status = '正常'
                warning_level = 0

            return {
                'rule': f'观察期(第{holding_days}天)-临时止损-3%',
                'price': stop_loss_price,
                'distance': f"{distance_pct:.2f}%",
                'warning_status': warning_status,
                'warning_level': warning_level
            }

        # 正式期(3天以上): 正式止损-5%
        else:
            stop_loss_price = cost * 0.95
            distance_pct = ((current_price - stop_loss_price) / stop_loss_price) * 100

            # 判断预警状态
            if current_price <= stop_loss_price:
                warning_status = '触发止损'
                warning_level = 3
            elif distance_pct <= 1:
                warning_status = '严重警告'
                warning_level = 2
            elif distance_pct <= 2:
                warning_status = '警告'
                warning_level = 1
            else:
                warning_status = '正常'
                warning_level = 0

            return {
                'rule': f'正式期(第{holding_days}天)-正式止损-5%',
                'price': stop_loss_price,
                'distance': f"{distance_pct:.2f}%",
                'warning_status': warning_status,
                'warning_level': warning_level
            }

    def _get_system_analysis(self, symbol: str, name: str) -> Dict:
        """获取系统分析建议"""
        try:
            if not self.system:
                return {
                    'recommendation': '无法分析',
                    'confidence': '0%',
                    'reason': '系统未初始化'
                }

            # 调用系统分析
            decision = self.system.analyze_stock(symbol, name, use_thread_safe=False)

            return {
                'recommendation': decision.action,
                'confidence': f"{decision.confidence:.0%}",
                'reason': decision.reason[:100] if decision.reason else ""
            }

        except Exception as e:
            self.logger.error(f"系统分析失败 {symbol}: {e}")
            return {
                'recommendation': '分析失败',
                'confidence': '0%',
                'reason': str(e)
            }

    def _generate_action_advice(self, profit_rate: float, stop_loss_info: Dict,
                               system_analysis: Dict, holding_days: int) -> Dict:
        """
        生成综合操作建议

        Args:
            profit_rate: 收益率（百分比）
            stop_loss_info: 止损信息
            system_analysis: 系统分析
            holding_days: 持仓天数

        Returns:
            操作建议字典
        """
        reasons = []
        risk_warning = ""
        next_action = ""

        # 解析系统建议和信心度
        system_action = system_analysis['recommendation']
        try:
            system_confidence = float(system_analysis['confidence'].replace('%', ''))
        except:
            system_confidence = 0

        warning_level = stop_loss_info.get('warning_level', 0)

        # 【最高优先级】触发止损
        if warning_level == 3:
            action = "强烈卖出-触发止损"
            reasons.append(f"当前价格已触及止损线{stop_loss_info['price']:.2f}元")
            reasons.append("风险控制要求立即卖出")
            risk_warning = "⚠️ 已触发止损，建议立即执行卖出操作"
            next_action = "立即挂单卖出"

        # 【次高优先级】严重警告 + 系统建议卖出
        elif warning_level == 2 or (warning_level == 1 and system_action == '卖出' and system_confidence >= 60):
            action = "减仓-风险警告"
            reasons.append(f"接近止损价{stop_loss_info['price']:.2f}元，距离{stop_loss_info['distance']}")
            if system_action == '卖出':
                reasons.append(f"系统建议卖出，信心度{system_analysis['confidence']}")
            reasons.append(f"当前收益率{profit_rate:+.2f}%")
            risk_warning = "⚠️ 风险较大，建议减仓观望"
            next_action = "考虑减仓30-50%，剩余仓位设置止损单"

        # 购买当日或观察期
        elif holding_days <= 3:
            if profit_rate >= 5:
                action = "继续持有-盈利良好"
                reasons.append(f"持仓{holding_days}天，盈利{profit_rate:.2f}%")
                reasons.append(f"系统建议{system_action}，信心度{system_analysis['confidence']}")
                risk_warning = "短期盈利不错，建议继续观察"
                next_action = "持有并关注后续走势"
            else:
                action = "继续持有-观察期"
                reasons.append(f"购买{holding_days}天，建议观察")
                reasons.append(f"当前收益率{profit_rate:+.2f}%")
                reasons.append(f"系统建议{system_action}，信心度{system_analysis['confidence']}")
                risk_warning = f"处于观察期，{'满3天后' if holding_days < 3 else ''}设置正式止损"
                next_action = f"继续观察{'至第3天' if holding_days < 3 else '，明日关注开盘'}"

        # 大幅盈利 - 考虑止盈
        elif profit_rate >= 30:
            action = "全部止盈-目标达成"
            reasons.append(f"盈利{profit_rate:.2f}%，达到止盈目标")
            reasons.append("建议全部卖出锁定利润")
            risk_warning = "大幅盈利，建议及时止盈"
            next_action = "分批卖出或全部止盈"

        elif profit_rate >= 15:
            action = "部分止盈-获利了结"
            reasons.append(f"盈利{profit_rate:.2f}%，建议部分止盈")
            reasons.append("可减仓30-50%锁定部分利润")
            if system_action == '卖出':
                reasons.append(f"系统也建议卖出，信心度{system_analysis['confidence']}")
            risk_warning = "盈利可观，建议部分止盈"
            next_action = "考虑卖出30-50%仓位"

        # 良好盈利 + 系统建议买入 - 考虑加仓
        elif 0 <= profit_rate <= 10 and system_action == '买入' and system_confidence >= 80:
            action = "考虑加仓-良好机会"
            reasons.append(f"当前盈利{profit_rate:.2f}%，状态良好")
            reasons.append(f"系统强烈建议买入，信心度{system_analysis['confidence']}")
            reasons.append("技术面或基本面出现买入信号")
            risk_warning = "有加仓机会，但需控制仓位"
            next_action = "可考虑加仓10-20%，设好止损"

        # 正常持有
        elif -3 <= profit_rate <= 15:
            action = "继续持有-正常状态"
            reasons.append(f"收益率{profit_rate:+.2f}%，在正常范围")
            reasons.append(f"系统建议{system_action}，信心度{system_analysis['confidence']}")
            if stop_loss_info['price']:
                reasons.append(f"止损价{stop_loss_info['price']:.2f}元，距离{stop_loss_info['distance']}")
            risk_warning = "状态正常，继续持有"
            next_action = "保持观察，关注止损线"

        # 轻度亏损
        elif -5 <= profit_rate < -3:
            action = "密切观察-轻度亏损"
            reasons.append(f"亏损{abs(profit_rate):.2f}%")
            reasons.append(f"距止损线{stop_loss_info['distance']}")
            reasons.append(f"系统建议{system_action}")
            risk_warning = "⚠️ 出现亏损，需密切关注"
            next_action = "严格设置止损单，防止进一步亏损"

        # 严重亏损但未触发止损
        else:
            action = "考虑减仓-亏损严重"
            reasons.append(f"亏损{abs(profit_rate):.2f}%")
            reasons.append("建议考虑减仓或止损")
            risk_warning = "⚠️ 亏损较大，建议及时止损"
            next_action = "评估是否继续持有，或执行止损"

        return {
            'action': action,
            'reasons': reasons,
            'risk_warning': risk_warning,
            'next_action': next_action
        }

    def _create_error_analysis(self, stock: Dict, error_msg: str) -> Dict:
        """创建错误分析结果"""
        return {
            "股票代码": stock.get('symbol', 'N/A'),
            "股票名称": stock.get('name', 'N/A'),
            "成本价": stock.get('cost', 0),
            "当前价格": 0,
            "持仓天数": 0,
            "购买日期": stock.get('purchase_date', 'N/A'),
            "持仓收益": 0,
            "持仓收益率": 0,
            "收益状态": "错误",
            "止损规则": "N/A",
            "止损价格": None,
            "距离止损": "N/A",
            "预警状态": "错误",
            "系统建议": "无法分析",
            "系统信心度": "0%",
            "系统理由": error_msg,
            "操作建议": "数据错误-无法建议",
            "建议理由": [error_msg],
            "风险提示": "数据获取失败",
            "下一步行动": "检查股票代码或网络连接",
            "当日最高": 0,
            "当日最低": 0,
            "当日涨跌": 0
        }