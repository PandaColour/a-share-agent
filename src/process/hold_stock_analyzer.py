# -*- coding: utf-8 -*-
"""
持仓分析器
负责分析持仓股票的收益、止损和操作建议
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import pandas as pd
from src.utils.hold_stock_io import (
    BUY_STATUS,
    SELL_STATUS,
    WATCH_STATUS,
    normalize_buy_flag,
)

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

    def _get_trailing_stop_drawdown(self) -> float:
        """
        获取追踪止损回撤阈值配置

        Returns:
            float: 追踪止损回撤阈值 (默认0.08，即8%)
        """
        if not self.config:
            return 0.08  # 默认值

        try:
            # 从analysis_settings读取
            analysis_risk = self.config.get_analysis_config().get('risk_management', {})
            trailing_stop_drawdown = analysis_risk.get('trailing_stop_drawdown', None)

            if trailing_stop_drawdown is not None:
                # 验证范围 [0.01, 0.50]
                if trailing_stop_drawdown < 0.01:
                    self.logger.warning(f"追踪止损回撤阈值 {trailing_stop_drawdown:.1%} 过低，使用最小值 1%")
                    return 0.01
                if trailing_stop_drawdown > 0.50:
                    self.logger.warning(f"追踪止损回撤阈值 {trailing_stop_drawdown:.1%} 过高，使用最大值 50%")
                    return 0.50
                return trailing_stop_drawdown

            # 回退到默认值
            self.logger.debug("未配置trailing_stop_drawdown，使用默认值 8%")
            return 0.08

        except Exception as e:
            self.logger.warning(f"读取追踪止损配置失败: {e}，使用默认值 8%")
            return 0.08

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
            cost = float(stock.get('cost', 0) or 0)
            purchase_date = stock.get('purchase_date', '未知')
            holding_status = normalize_buy_flag(stock.get('buy_flag', BUY_STATUS))

            self.logger.info(f"开始分析持仓股票: {name}({symbol})")

            # 1. 获取当前价格
            current_price, price_info = self._get_current_price(symbol)

            if current_price is None or current_price == 0:
                return self._create_error_analysis(stock, "无法获取当前价格")

            # 2. 计算持仓天数
            holding_days = self._calculate_holding_days(purchase_date)

            # 3. 计算收益
            cost_basis = cost if cost > 0 else current_price
            profit_loss = current_price - cost_basis
            profit_loss_rate = (profit_loss / cost_basis) * 100 if cost_basis > 0 else 0

            # 4. 确定收益状态
            profit_status = self._determine_profit_status(profit_loss_rate)

            # 5. 计算止损价格和状态（传递symbol和purchase_date用于计算持仓期间最高价）
            stop_loss_info = self._calculate_stop_loss(
                cost, holding_days, current_price, symbol, purchase_date
            )

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
                holding_days,
                holding_status=holding_status,
                current_price=current_price,
                cost=cost_basis
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
                "持仓状态": holding_status,

                # 收益分析
                "持仓收益": profit_loss,
                "持仓收益率": profit_loss_rate,
                "收益状态": profit_status,

                # 追踪止损分析
                "止损规则": stop_loss_info['rule'],
                "止损价格": stop_loss_info['price'],
                "距离止损": stop_loss_info['distance'],
                "预警状态": stop_loss_info['warning_status'],
                "持仓最高价": stop_loss_info.get('highest_price', cost),
                "最高价回撤": stop_loss_info.get('drawdown_from_peak', 'N/A'),

                # 系统分析
                "系统建议": system_analysis['recommendation'],
                "系统信心度": system_analysis['confidence'],
                "系统理由": system_analysis['reason'],

                # 综合建议
                "操作建议": action_advice['action'],
                "建议理由": action_advice['reasons'],
                "风险提示": action_advice['risk_warning'],
                "下一步行动": action_advice['next_action'],
                "观察状态": action_advice.get('observation_status', '未观察'),
                "状态更新": action_advice.get('state_update', {}),

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
                            current_price: float, symbol: str = None,
                            purchase_date: str = None) -> Dict:
        """
        计算追踪止损价格和状态

        新逻辑：
        - 买入后跟踪最高价格
        - 从最高价回撤8%时触发止损

        Args:
            cost: 成本价
            holding_days: 持仓天数
            current_price: 当前价格
            symbol: 股票代码（用于获取历史数据）
            purchase_date: 购买日期（用于计算持仓期间最高价）

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
                'warning_level': 0,
                'highest_price': cost
            }

        # 计算持仓期间的最高价
        highest_price = self._get_highest_price_since_purchase(
            symbol, purchase_date, current_price, cost
        )

        # 追踪止损规则：从最高价回撤指定阈值(可配置)
        trailing_stop_rate = self._get_trailing_stop_drawdown()
        stop_loss_price = highest_price * (1 - trailing_stop_rate)

        # 计算距离止损线的距离
        distance_pct = ((current_price - stop_loss_price) / stop_loss_price) * 100

        # 计算从最高价的回撤比例
        drawdown_from_peak = ((current_price - highest_price) / highest_price) * 100

        # 判断预警状态
        if current_price <= stop_loss_price:
            warning_status = '触发追踪止损'
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
            'rule': f'追踪止损(持仓{holding_days}天)-最高价回撤{trailing_stop_rate:.1%}',
            'price': stop_loss_price,
            'distance': f"{distance_pct:.2f}%",
            'warning_status': warning_status,
            'warning_level': warning_level,
            'highest_price': highest_price,
            'drawdown_from_peak': f"{drawdown_from_peak:.2f}%"
        }

    def _get_highest_price_since_purchase(self, symbol: str, purchase_date: str,
                                         current_price: float, cost: float) -> float:
        """
        获取从购买日期到现在的最高价

        Args:
            symbol: 股票代码
            purchase_date: 购买日期
            current_price: 当前价格
            cost: 成本价

        Returns:
            最高价格
        """
        try:
            if not symbol or not purchase_date or purchase_date == '未知':
                # 如果没有历史数据，使用当前价格和成本价的较大值
                return max(current_price, cost)

            if not self.system or not hasattr(self.system, 'data_provider'):
                return max(current_price, cost)

            # 获取从购买日期到现在的历史数据
            from datetime import datetime
            start_date = purchase_date
            end_date = datetime.now().strftime('%Y-%m-%d')

            # 获取历史数据
            data, _, _, _, _, _ = self.system.data_provider.get_stock_data(
                symbol, start_date=start_date, end_date=end_date
            )

            if data is None or data.empty:
                return max(current_price, cost)

            # 计算最高价
            highest_price = data['High'].max()

            # 确保最高价不低于成本价和当前价格
            highest_price = max(highest_price, current_price, cost)

            self.logger.debug(f"{symbol} 持仓期间最高价: {highest_price:.2f}, 当前价: {current_price:.2f}")

            return highest_price

        except Exception as e:
            self.logger.warning(f"获取最高价失败 {symbol}: {e}")
            # 发生错误时，使用当前价格和成本价的较大值
            return max(current_price, cost)

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
                               system_analysis: Dict, holding_days: int,
                               holding_status: str = BUY_STATUS,
                               current_price: float = 0.0,
                               cost: float = 0.0) -> Dict:
        """
        生成综合操作建议（支持追踪止损）

        Args:
            profit_rate: 收益率（百分比）
            stop_loss_info: 止损信息（包含追踪止损相关字段）
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
        highest_price = stop_loss_info.get('highest_price', 0)
        drawdown_from_peak = stop_loss_info.get('drawdown_from_peak', 'N/A')

        observation_advice = self._generate_observation_advice(
            holding_status=holding_status,
            system_action=system_action,
            system_confidence=system_analysis['confidence'],
            holding_days=holding_days,
            current_price=current_price,
            cost=cost,
            profit_rate=profit_rate
        )
        if observation_advice:
            return observation_advice

        # 【最高优先级】触发追踪止损
        if warning_level == 3:
            action = "强烈卖出-触发追踪止损"
            reasons.append(f"从最高价{highest_price:.2f}元回撤{drawdown_from_peak}")
            reasons.append(f"当前价格已触及追踪止损线{stop_loss_info['price']:.2f}元")
            reasons.append("风险控制要求立即卖出")
            risk_warning = "⚠️ 已触发追踪止损，建议立即执行卖出操作"
            next_action = "立即挂单卖出"

        # 【次高优先级】严重警告 + 系统建议卖出
        elif warning_level == 2 or (warning_level == 1 and system_action.startswith('卖出') and system_confidence >= 60):
            action = "减仓-风险警告"
            reasons.append(f"接近追踪止损价{stop_loss_info['price']:.2f}元，距离{stop_loss_info['distance']}")
            reasons.append(f"持仓最高价{highest_price:.2f}元，当前回撤{drawdown_from_peak}")
            if system_action.startswith('卖出'):
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
                risk_warning = f"处于观察期，追踪止损保护中"
                next_action = f"继续观察{'至第3天' if holding_days < 3 else '，明日关注开盘'}"

        # 大幅盈利 - 考虑止盈
        elif profit_rate >= 30:
            action = "全部止盈-目标达成"
            reasons.append(f"盈利{profit_rate:.2f}%，达到止盈目标")
            reasons.append(f"持仓最高价{highest_price:.2f}元")
            reasons.append("建议全部卖出锁定利润")
            risk_warning = "大幅盈利，建议及时止盈"
            next_action = "分批卖出或全部止盈"

        elif profit_rate >= 15:
            action = "部分止盈-获利了结"
            reasons.append(f"盈利{profit_rate:.2f}%，建议部分止盈")
            reasons.append(f"持仓最高价{highest_price:.2f}元，当前回撤{drawdown_from_peak}")
            reasons.append("可减仓30-50%锁定部分利润")
            if system_action.startswith('卖出'):
                reasons.append(f"系统也建议卖出，信心度{system_analysis['confidence']}")
            risk_warning = "盈利可观，建议部分止盈"
            next_action = "考虑卖出30-50%仓位"

        # 良好盈利 + 系统建议买入 - 考虑加仓
        elif 0 <= profit_rate <= 10 and system_action == '买入' and system_confidence >= 80:
            action = "考虑加仓-良好机会"
            reasons.append(f"当前盈利{profit_rate:.2f}%，状态良好")
            reasons.append(f"系统强烈建议买入，信心度{system_analysis['confidence']}")
            reasons.append("技术面或基本面出现买入信号")
            reasons.append(f"追踪止损价{stop_loss_info['price']:.2f}元保护中")
            risk_warning = "有加仓机会，但需控制仓位"
            next_action = "可考虑加仓10-20%，追踪止损自动保护"

        # 正常持有
        elif -3 <= profit_rate <= 15:
            action = "继续持有-正常状态"
            reasons.append(f"收益率{profit_rate:+.2f}%，在正常范围")
            reasons.append(f"系统建议{system_action}，信心度{system_analysis['confidence']}")
            if stop_loss_info['price']:
                reasons.append(f"追踪止损价{stop_loss_info['price']:.2f}元，距离{stop_loss_info['distance']}")
            if highest_price > 0:
                reasons.append(f"持仓最高价{highest_price:.2f}元")
            risk_warning = "状态正常，继续持有"
            next_action = "保持观察，追踪止损自动保护"

        # 轻度亏损
        elif -5 <= profit_rate < -3:
            action = "密切观察-轻度亏损"
            reasons.append(f"亏损{abs(profit_rate):.2f}%")
            reasons.append(f"距追踪止损线{stop_loss_info['distance']}")
            reasons.append(f"系统建议{system_action}")
            risk_warning = "⚠️ 出现亏损，需密切关注"
            next_action = "严格观察追踪止损线，防止进一步亏损"

        # 严重亏损但未触发止损
        else:
            action = "考虑减仓-亏损严重"
            reasons.append(f"亏损{abs(profit_rate):.2f}%")
            reasons.append(f"距追踪止损线{stop_loss_info['distance']}")
            reasons.append("建议考虑减仓或等待止损")
            risk_warning = "⚠️ 亏损较大，追踪止损会自动触发"
            next_action = "评估是否手动止损，或等待追踪止损触发"

        return {
            'action': action,
            'reasons': reasons,
            'risk_warning': risk_warning,
            'next_action': next_action,
            'observation_status': '未观察',
            'state_update': {}
        }

    def _generate_observation_advice(self, holding_status: str, system_action: str,
                                     system_confidence: str, holding_days: int,
                                     current_price: float, cost: float,
                                     profit_rate: float) -> Optional[Dict]:
        """为 sell/watch 状态生成观察买入建议和状态更新。"""
        today_str = self.today.strftime('%Y-%m-%d')
        rounded_price = round(float(current_price), 2)

        if holding_status == SELL_STATUS:
            if system_action == '买入':
                return {
                    'action': '进入观察-等待确认买入',
                    'reasons': [
                        f"AI输出买入信号，信心度{system_confidence}",
                        f"以当前价{rounded_price:.2f}元设为观察点",
                        "等待3天后确认收盘价是否高于观察点"
                    ],
                    'risk_warning': '未实际持仓，仅进入买入观察',
                    'next_action': '观察3天，若价格高于观察点且AI仍建议买入，再确认买入',
                    'observation_status': '进入观察',
                    'state_update': {
                        'buy_flag': WATCH_STATUS,
                        'purchase_date': today_str,
                        'cost': rounded_price
                    }
                }

            return {
                'action': '继续观察-等待买入信号',
                'reasons': [
                    f"当前为sell状态，AI建议{system_action}",
                    f"按记录成本测算收益率{profit_rate:+.2f}%"
                ],
                'risk_warning': '未实际持仓，等待新的买入信号',
                'next_action': '继续跟踪，AI输出买入时再进入3天观察',
                'observation_status': '等待买入信号',
                'state_update': {}
            }

        if holding_status != WATCH_STATUS:
            return None

        if system_action.startswith('卖出'):
            return {
                'action': '观察取消-出现卖出信号',
                'reasons': [
                    f"观察期间AI输出{system_action}",
                    "买入观察循环结束"
                ],
                'risk_warning': '未确认买入，不执行买入',
                'next_action': '状态回到sell，等待下一次买入信号',
                'observation_status': '观察取消',
                'state_update': {
                    'buy_flag': SELL_STATUS
                }
            }

        if holding_days < 3:
            return {
                'action': '继续观察-未满确认期',
                'reasons': [
                    f"观察{holding_days}天，未满3天",
                    f"观察点价格{cost:.2f}元，当前价格{current_price:.2f}元",
                    f"AI建议{system_action}，信心度{system_confidence}"
                ],
                'risk_warning': '未实际持仓，暂不确认买入',
                'next_action': '继续等待至第3天确认收盘价',
                'observation_status': '观察中',
                'state_update': {}
            }

        if current_price > cost and system_action == '买入':
            return {
                'action': '确认可以买入-观察达标',
                'reasons': [
                    f"观察{holding_days}天后当前价{current_price:.2f}元高于观察点{cost:.2f}元",
                    f"AI仍输出买入，信心度{system_confidence}"
                ],
                'risk_warning': '满足观察买入条件，仍需按实际交易纪律控制仓位',
                'next_action': '确认可以买入，买入后在持仓配置中标记为buy并更新成本',
                'observation_status': '确认可以买入',
                'state_update': {}
            }

        if current_price <= cost:
            return {
                'action': '观察重置-价格未突破',
                'reasons': [
                    f"观察{holding_days}天后当前价{current_price:.2f}元未高于观察点{cost:.2f}元",
                    "按当天价格重置观察点，继续等待3天"
                ],
                'risk_warning': '买入条件未满足，继续观察',
                'next_action': '已重置观察点，继续等待下一次3天确认',
                'observation_status': '观察重置',
                'state_update': {
                    'buy_flag': WATCH_STATUS,
                    'purchase_date': today_str,
                    'cost': rounded_price
                }
            }

        return {
            'action': '继续观察-AI未确认买入',
            'reasons': [
                f"当前价{current_price:.2f}元高于观察点{cost:.2f}元",
                f"但AI建议{system_action}，未确认买入"
            ],
            'risk_warning': '价格条件满足但AI未确认买入',
            'next_action': '继续观察，等待AI重新输出买入',
            'observation_status': '观察中',
            'state_update': {}
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
            "持仓状态": normalize_buy_flag(stock.get('buy_flag', BUY_STATUS)),
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
            "观察状态": "错误",
            "状态更新": {},
            "当日最高": 0,
            "当日最低": 0,
            "当日涨跌": 0
        }
