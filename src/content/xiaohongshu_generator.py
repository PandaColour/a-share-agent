# -*- coding: utf-8 -*-
"""
小红书文案生成器
基于股票分析结果生成小红书风格的投资分析文案
"""

import os
import json
import logging
import re
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class XiaohongshuContentGenerator:
    """小红书文案生成器"""

    def __init__(self, agent_type: str = "codex", agent_factory=None):
        """
        初始化文案生成器

        Args:
            agent_type: CLI Agent 类型，当前默认使用 codex
            agent_factory: Agent 工厂，测试时可注入
        """
        self.agent_type = agent_type
        self.agent_factory = agent_factory
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """加载 prompt 模板"""
        try:
            prompt_file = Path("config/xiaohongshu_prompt.md")
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning(f"Prompt 模板文件不存在: {prompt_file}")
                return self._get_default_prompt()
        except Exception as e:
            logger.error(f"加载 prompt 模板失败: {e}")
            return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """获取默认 prompt（作为备用）"""
        return """
你是一位专业的股票分析师，正在为小红书平台撰写每日股票分析内容。
请根据提供的持仓数据、买入推荐和卖出预警生成一篇小红书风格的文案。

要求：
1. 使用小红书风格，轻松易懂，适当使用emoji
2. 包含三部分：持仓实况、值得关注的机会、风险提示
3. 字数控制在800-1200字
4. 必须包含免责声明
"""

    def generate_content(
        self,
        output_dir: str,
        holdings_csv: str = "holdings_analysis.csv",
        analysis_csv: str = "analysis_summary.csv"
    ) -> Optional[str]:
        """
        生成小红书文案

        Args:
            output_dir: 输出目录路径
            holdings_csv: 持仓分析CSV文件名
            analysis_csv: 分析汇总CSV文件名

        Returns:
            生成的文案内容，失败返回None
        """
        try:
            logger.info(f"开始生成小红书文案，输出目录: {output_dir}")

            # 1. 读取数据文件
            holdings_data = self._load_holdings_data(output_dir, holdings_csv)
            analysis_data = self._load_analysis_data(output_dir, analysis_csv)

            # 检查是否有可用数据（DataFrame需要用.empty判断，而不是直接用not）
            holdings_empty = holdings_data is None or (hasattr(holdings_data, 'empty') and holdings_data.empty)
            analysis_empty = analysis_data is None or (hasattr(analysis_data, 'empty') and analysis_data.empty)

            if holdings_empty and analysis_empty:
                logger.warning("没有可用的分析数据，跳过文案生成")
                return None

            # 2. 准备数据
            holdings_list = self._prepare_holdings_data(holdings_data, analysis_data)
            buy_recommendations = self._prepare_buy_recommendations(analysis_data, holdings_data)
            sell_warnings = self._prepare_sell_warnings(analysis_data, holdings_data)

            # 2.1 从回测历史中提取最近买入的股票（补充推荐）
            # 注意：使用15天而不是5天，因为回测数据更新频率可能不是每天
            backtest_buys = self._extract_recent_buys_from_backtest(output_dir, days=15)
            if backtest_buys:
                # 合并回测推荐，并去重（基于symbol）
                existing_symbols = {rec['symbol'] for rec in buy_recommendations}
                for backtest_buy in backtest_buys:
                    if backtest_buy['symbol'] not in existing_symbols:
                        buy_recommendations.append(backtest_buy)
                        existing_symbols.add(backtest_buy['symbol'])
                logger.info(f"合并回测推荐后，买入推荐总数: {len(buy_recommendations)}")

            # 3. 构建 AI 输入
            ai_input = self._build_ai_input(holdings_list, buy_recommendations, sell_warnings)

            # 4. 使用 CLI Agent 生成文案，工作目录固定为当天输出目录
            logger.info(f"使用 {self.agent_type} CLI Agent 生成文案")
            content = self._generate_with_agent(ai_input, output_dir)

            # 5. 保存文案
            if content:
                self._save_content(output_dir, content)
                logger.info("小红书文案生成成功")
                return content
            else:
                logger.error("文案生成失败")
                return None

        except Exception as e:
            logger.error(f"生成小红书文案失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _load_holdings_data(self, output_dir: str, filename: str) -> Optional[pd.DataFrame]:
        """加载持仓数据"""
        try:
            filepath = Path(output_dir) / filename
            if filepath.exists():
                df = pd.read_csv(filepath, encoding='utf-8-sig')
                logger.info(f"加载持仓数据: {len(df)} 条记录")
                return df
            else:
                logger.warning("当前没有持仓")
                return None
        except Exception as e:
            logger.error(f"加载持仓数据失败: {e}")
            return None

    def _load_analysis_data(self, output_dir: str, filename: str) -> Optional[pd.DataFrame]:
        """加载分析数据"""
        try:
            filepath = Path(output_dir) / filename
            if filepath.exists():
                df = pd.read_csv(filepath, encoding='utf-8-sig')
                logger.info(f"加载分析数据: {len(df)} 条记录")
                return df
            else:
                logger.warning(f"分析数据文件不存在: {filepath}")
                return None
        except Exception as e:
            logger.error(f"加载分析数据失败: {e}")
            return None

    def _prepare_holdings_data(
        self,
        holdings_df: Optional[pd.DataFrame],
        analysis_df: Optional[pd.DataFrame]
    ) -> List[Dict]:
        """准备持仓数据"""
        if holdings_df is None or holdings_df.empty:
            return []

        holdings_list = []
        for _, row in holdings_df.iterrows():
            symbol = row.get('股票代码', '')
            name = row.get('股票名称', '')
            holding_days = row.get('持仓天数', 0)
            profit_rate = row.get('持仓收益率', '0%')
            system_action = row.get('操作建议', '持有')
            confidence = row.get('系统建议', '').split('(')[-1].replace(')', '') if '(' in str(row.get('系统建议', '')) else '50%'
            reason = row.get('建议理由', '')

            # 从分析数据中获取对应股票的分析结果（如果有）
            analysis_action = system_action
            analysis_confidence = confidence
            analysis_reason = reason

            if analysis_df is not None and not analysis_df.empty:
                matching = analysis_df[analysis_df['股票代码'] == symbol]
                if not matching.empty:
                    analysis_action = matching.iloc[0].get('操作建议', system_action)
                    analysis_confidence = matching.iloc[0].get('信心度', confidence)
                    analysis_reason = matching.iloc[0].get('决策理由', reason)

            holdings_list.append({
                'symbol': symbol,
                'name': name,
                'holding_days': holding_days,
                'profit_rate': profit_rate,
                'analysis_action': analysis_action,
                'confidence': analysis_confidence,
                'reason': analysis_reason or reason
            })

        logger.info(f"准备持仓数据: {len(holdings_list)} 只股票")
        return holdings_list

    def _prepare_buy_recommendations(
        self,
        analysis_df: Optional[pd.DataFrame],
        holdings_df: Optional[pd.DataFrame]
    ) -> List[Dict]:
        """准备买入推荐数据（排除已持仓股票）"""
        if analysis_df is None or analysis_df.empty:
            return []

        # 获取持仓股票代码列表
        holding_symbols = set()
        if holdings_df is not None and not holdings_df.empty:
            holding_symbols = set(holdings_df['股票代码'].tolist())

        # 筛选买入推荐（排除持仓股票）
        buy_df = analysis_df[
            (analysis_df['操作建议'] == '买入') &
            (~analysis_df['股票代码'].isin(holding_symbols))
        ]

        buy_list = []
        for _, row in buy_df.iterrows():
            buy_list.append({
                'symbol': row.get('股票代码', ''),
                'name': row.get('股票名称', ''),
                'confidence': row.get('信心度', '50%'),
                'reason': row.get('决策理由', ''),
                'news': ''  # TODO: 从新闻数据中获取
            })

        logger.info(f"准备买入推荐: {len(buy_list)} 只股票")
        return buy_list

    def _prepare_sell_warnings(
        self,
        analysis_df: Optional[pd.DataFrame],
        holdings_df: Optional[pd.DataFrame]
    ) -> List[Dict]:
        """准备卖出预警数据（排除已持仓且准备卖出的股票）"""
        if analysis_df is None or analysis_df.empty:
            return []

        # 获取持仓中准备卖出的股票代码
        selling_symbols = set()
        if holdings_df is not None and not holdings_df.empty:
            for _, row in holdings_df.iterrows():
                if '卖出' in str(row.get('操作建议', '')):
                    selling_symbols.add(row.get('股票代码', ''))

        # 筛选卖出预警（排除持仓中已处理的）
        sell_df = analysis_df[
            (analysis_df['操作建议'].str.startswith('卖出')) &
            (~analysis_df['股票代码'].isin(selling_symbols))
        ]

        sell_list = []
        for _, row in sell_df.iterrows():
            sell_list.append({
                'symbol': row.get('股票代码', ''),
                'name': row.get('股票名称', ''),
                'reason': row.get('决策理由', '')
            })

        logger.info(f"准备卖出预警: {len(sell_list)} 只股票")
        return sell_list

    def _extract_recent_buys_from_backtest(self, output_dir: str, days: int = 5) -> List[Dict]:
        """
        从回测交易历史中提取最近N天内的买入股票

        逻辑：
        1. 找到每个股票最后一个买入记录
        2. 检查该买入之后是否有策略卖出（排除强制平仓）
        3. 如果没有策略卖出且买入在最近N天内，则加入推荐列表

        Args:
            output_dir: 输出目录路径
            days: 天数范围，默认为5天

        Returns:
            提取的股票列表
        """
        try:
            # 检查文件是否存在
            backtest_file = Path(output_dir) / "backtest_trade_history.json"
            if not backtest_file.exists():
                logger.debug(f"回测交易历史文件不存在: {backtest_file}")
                return []

            # 读取JSON文件
            with open(backtest_file, 'r', encoding='utf-8') as f:
                trade_history = json.load(f)

            if not trade_history:
                logger.debug("回测交易历史为空")
                return []

            # 计算截止日期（最近N天）
            today = datetime.now()
            cutoff_date = (today - pd.Timedelta(days=days)).strftime('%Y-%m-%d')

            # 按symbol分组交易记录
            symbol_trades = {}
            for record in trade_history:
                symbol = record.get('symbol', '')
                if symbol:
                    if symbol not in symbol_trades:
                        symbol_trades[symbol] = []
                    symbol_trades[symbol].append(record)

            # 提取满足条件的股票
            recent_buys = []
            for symbol, trades in symbol_trades.items():
                # 按日期排序
                sorted_trades = sorted(trades, key=lambda x: x.get('date', ''))

                if not sorted_trades:
                    continue

                # 找到最后一个买入记录
                last_buy_idx = None
                for i in range(len(sorted_trades) - 1, -1, -1):
                    if sorted_trades[i].get('action') == '买入':
                        last_buy_idx = i
                        break

                if last_buy_idx is None:
                    continue

                last_buy = sorted_trades[last_buy_idx]

                # 检查该买入之后是否有策略卖出（排除强制平仓）
                has_strategy_sell = False
                for i in range(last_buy_idx + 1, len(sorted_trades)):
                    trade = sorted_trades[i]
                    if (trade.get('action', '').startswith('卖出') and
                        trade.get('reason') == '主动卖出'):
                        has_strategy_sell = True
                        break

                # 如果没有策略卖出，且买入在最近N天内
                if (not has_strategy_sell and
                    last_buy.get('date', '') >= cutoff_date):
                    recent_buys.append({
                        'symbol': last_buy['symbol'],
                        'name': last_buy.get('name', last_buy['symbol']),
                        'date': last_buy['date'],
                        'confidence': '系统回测',
                        'reason': f"回测在{last_buy['date']}检测到买入信号",
                        'news': '',
                        'from_backtest': True
                    })

            logger.info(f"从回测历史中提取到 {len(recent_buys)} 只最近{days}天买入的股票（排除已策略卖出）")
            return recent_buys

        except json.JSONDecodeError as e:
            logger.warning(f"回测交易历史JSON格式错误: {e}")
            return []
        except Exception as e:
            logger.warning(f"提取回测买入股票失败: {e}")
            return []

    def _build_ai_input(
        self,
        holdings_list: List[Dict],
        buy_recommendations: List[Dict],
        sell_warnings: List[Dict]
    ) -> str:
        """构建 AI 输入"""
        # 获取交易日信息（包含日期、星期几、本周第几个交易日等）
        try:
            from src.utils.trading_calendar import get_current_trading_day_info
            trading_day_info = get_current_trading_day_info()
        except Exception as e:
            logger.warning(f"获取交易日信息失败: {e}，使用默认日期")
            trading_day_info = {
                'current_date': datetime.now().strftime('%Y年%m月%d日'),
                'weekday_cn': '未知',
                'week_trading_day_num': 0,
                'is_trading_day': True,
                'holiday_info': {'is_holiday_week': False},
                'summary_text': ''
            }

        data_json = {
            'holdings_data': holdings_list,
            'buy_recommendations': buy_recommendations,
            'sell_warnings': sell_warnings,
            'analysis_date': trading_day_info['current_date'],
            'trading_day_info': {
                'weekday': trading_day_info['weekday_cn'],
                'week_trading_day_num': trading_day_info['week_trading_day_num'],
                'is_trading_day': trading_day_info['is_trading_day'],
                'holiday_info': trading_day_info['holiday_info'],
                'date_summary': trading_day_info['summary_text']
            }
        }

        ai_input = f"{self.prompt_template}\n\n## 输入数据\n\n```json\n{json.dumps(data_json, ensure_ascii=False, indent=2)}\n```\n\n请生成小红书文案："
        return ai_input

    def _create_agent(self, output_dir: str):
        """创建用于生成文案的 CLI Agent"""
        agent_factory = self.agent_factory
        if agent_factory is None:
            from src.agents import Agent
            agent_factory = Agent

        return agent_factory(
            name="小红书文案生成器",
            system_prompt_file=None,
            work_dir=str(output_dir),
            agent_type=self.agent_type,
        )

    def _generate_with_agent(self, ai_input: str, output_dir: str) -> Optional[str]:
        """使用 CLI Agent 生成文案"""
        try:
            logger.info("调用 CLI Agent 生成小红书文案...")
            content = self._create_agent(output_dir).send_message(ai_input)
            if content:
                logger.info(f"CLI Agent 生成文案成功，长度: {len(content)}")
                return content
            else:
                logger.warning("CLI Agent 返回空内容")
                return None
        except Exception as e:
            logger.error(f"CLI Agent 生成文案失败: {e}")
            return None

    def _generate_with_template(
        self,
        holdings_list: List[Dict],
        buy_recommendations: List[Dict],
        sell_warnings: List[Dict]
    ) -> str:
        """使用模板生成文案（备用方案）"""
        lines = []
        lines.append(f"📊 {datetime.now().strftime('%Y年%m月%d日')} 股市观察 | AI量化分析报告\n")

        # 持仓部分
        if holdings_list:
            lines.append("## 💼 我的持仓实况\n")
            for i, stock in enumerate(holdings_list, 1):
                profit_emoji = "📈" if "+" in stock['profit_rate'] else "📉"
                lines.append(f"{i}. **{stock['name']} ({stock['symbol']})** {profit_emoji}")
                lines.append(f"   - 持有{stock['holding_days']}天，收益率 {stock['profit_rate']}")
                lines.append(f"   - AI建议：{stock['analysis_action']}（信心度{stock['confidence']}）")
                lines.append(f"   - 理由：{stock['reason'][:100]}...\n")

        # 买入推荐部分
        if buy_recommendations:
            lines.append("## ⭐ 本周值得关注的机会\n")
            for i, stock in enumerate(buy_recommendations[:5], 1):  # 最多5只
                lines.append(f"{i}. **{stock['name']} ({stock['symbol']})** - 信心度{stock['confidence']}")
                lines.append(f"   - {stock['reason'][:100]}...\n")

        # 卖出预警部分
        if sell_warnings:
            lines.append("## ⚠️ 风险提示\n")
            for i, stock in enumerate(sell_warnings[:5], 1):  # 最多5只
                lines.append(f"{i}. **{stock['name']} ({stock['symbol']})** - {stock['reason'][:80]}...\n")

        # 免责声明
        lines.append("\n---\n")
        lines.append("⚠️ 免责声明：以上内容为AI量化模型分析结果，仅供学习参考，不构成投资建议。投资有风险，入市需谨慎！\n")

        return '\n'.join(lines)

    def _convert_markdown_to_plain_text(self, content: str) -> str:
        """生成适合直接粘贴到微信原生编辑器的纯文本副本"""
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
        text = text.replace("**", "").replace("__", "").replace("`", "")

        plain_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                plain_lines.append("")
                continue
            stripped = re.sub(r"^#{1,6}\s*", "", stripped)
            stripped = re.sub(r"^[-*+]\s+", "", stripped)
            stripped = re.sub(r"^\d+\.\s+", "", stripped)
            plain_lines.append(stripped)

        return "\n".join(plain_lines)

    def _save_content(self, output_dir: str, content: str):
        """保存文案到文件"""
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # 保存为 Markdown 文件
            md_file = output_path / "xiaohongshu_content.md"
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"小红书文案已保存: {md_file}")

            # 保存为 TXT 文件（方便复制）
            txt_file = output_path / "xiaohongshu_content.txt"
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(self._convert_markdown_to_plain_text(content))
            logger.info(f"小红书文案已保存: {txt_file}")

        except Exception as e:
            logger.error(f"保存文案失败: {e}")
