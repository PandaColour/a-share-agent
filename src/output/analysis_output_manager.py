# -*- coding: utf-8 -*-
"""
分析输出管理器

负责格式化、打印和保存分析结果
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AnalysisOutputManager:
    """分析输出管理器"""

    def __init__(self):
        """初始化输出管理器"""
        self.logger = logging.getLogger(__name__)

    def format_analysis_result(
        self,
        symbol: str,
        name: str,
        decision,
        data,
        analyses: List[Dict],
        include_analyst_details: bool = True
    ) -> Dict:
        """
        格式化单个分析结果为输出字典

        Args:
            symbol: 股票代码
            name: 股票名称
            decision: 交易决策对象
            data: 股票数据
            analyses: 分析师分析结果列表
            include_analyst_details: 是否包含分析师详情

        Returns:
            格式化的结果字典
        """
        from utils.consecutive_change_calculator import (
            calculate_consecutive_changes,
            format_consecutive_days,
            format_consecutive_change
        )

        # 格式化涨跌幅显示
        change_display = ""
        if decision.daily_change_percent != 0:
            change_sign = "+" if decision.daily_change_percent > 0 else ""
            change_display = f"{change_sign}{decision.daily_change_percent:.2f}%"
        else:
            change_display = "0.00%"

        # 计算连续涨跌统计
        consecutive_stats = calculate_consecutive_changes(data)
        consecutive_days_display = format_consecutive_days(consecutive_stats['consecutive_days'])
        consecutive_change_display = format_consecutive_change(consecutive_stats['consecutive_change'])

        # 基本结果
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
            "连续涨跌日": consecutive_days_display,
            "连续涨跌幅度": consecutive_change_display,
            "分析时间": decision.timestamp,
            "决策理由": decision.reason
        }

        # 添加分析师详情
        if include_analyst_details and analyses:
            result["分析师详情"] = self._format_analyst_details(analyses)

        # 添加多轮辩论详情（如果有）
        if hasattr(decision, 'multi_round_debate_result') and decision.multi_round_debate_result:
            debate_detail = self._format_debate_details(decision.multi_round_debate_result)
            if debate_detail and include_analyst_details:
                result["分析师详情"]["多轮辩论分析师"] = debate_detail

        # 添加目标价格信息（如果有）
        if hasattr(decision, 'target_price_medium') and decision.target_price_medium > 0:
            price_targets = self._format_price_targets(decision)
            result.update(price_targets)

        return result

    def _format_analyst_details(self, analyses: List[Dict]) -> Dict:
        """格式化分析师详情"""
        analyst_details = {}

        # 准备分析师输入信息（所有分析师共享相同的输入）
        analyst_inputs = {}
        if analyses:
            analyst_inputs = analyses[0].get("analyst_inputs", {})

        # 格式化各个分析师的结果
        for analysis in analyses:
            analyst_type = analysis.get("analyst_type", "")

            if analyst_type == "基本面分析":
                analyst_details["基本面分析师"] = {
                    "输入信息": analyst_inputs.copy(),
                    "输出结果": {
                        "推荐操作": analysis.get("recommendation", "持有"),
                        "信心度": f"{analysis.get('confidence', 0.5):.2%}",
                        "推理过程": analysis.get("reasoning", []),
                        "估值状况": analysis.get("valuation_status", "N/A"),
                        "财务健康": analysis.get("financial_health", "N/A"),
                        "目标价格区间": analysis.get("target_price_range", {"low": 0, "high": 0})
                    }
                }
            elif analyst_type == "技术面分析":
                analyst_details["技术面分析师"] = {
                    "输入信息": analyst_inputs.copy(),
                    "输出结果": {
                        "推荐操作": analysis.get("recommendation", "持有"),
                        "信心度": f"{analysis.get('confidence', 0.5):.2%}",
                        "推理过程": analysis.get("reasoning", []),
                        "技术指标": analysis.get("technical_indicators", {}),
                        "趋势分析": analysis.get("trend_analysis", "N/A")
                    }
                }
            elif analyst_type == "情感面分析":
                analyst_details["情感面分析师"] = {
                    "输入信息": analyst_inputs.copy(),
                    "输出结果": {
                        "推荐操作": analysis.get("recommendation", "持有"),
                        "信心度": f"{analysis.get('confidence', 0.5):.2%}",
                        "推理过程": analysis.get("reasoning", []),
                        "市场情绪": analysis.get("market_sentiment", "中性"),
                        "新闻分析": analysis.get("news_analysis", {})
                    }
                }
            elif analyst_type == "AI因子分析":
                analyst_details["AI因子分析师"] = {
                    "输入信息": analyst_inputs.copy(),
                    "输出结果": {
                        "推荐操作": analysis.get("recommendation", "N/A"),
                        "信心度": f"{analysis.get('confidence', 0.5):.2%}",
                        "推理过程": analysis.get("reasoning", []),
                        "因子详情": analysis.get("factor_details", {}),
                        "因子总结": analysis.get("factor_summary", {})
                    }
                }

        return analyst_details

    def _format_debate_details(self, debate_result: Dict) -> Dict:
        """格式化多轮辩论详情"""
        try:
            debate_summary = debate_result.get("debate_summary", {})
            final_decision = debate_result.get("final_decision", {})
            debate_rounds = debate_result.get("debate_rounds", [])

            # 提取看涨和看跌的主要观点
            bull_arguments = []
            bear_arguments = []
            for round_data in debate_rounds:
                speaker = round_data.get("speaker", "")
                response = round_data.get("response", "")
                if speaker == "Bull":
                    bull_arguments.append(f"第{round_data.get('round', 0)}轮: {response[:200]}...")
                elif speaker == "Bear":
                    bear_arguments.append(f"第{round_data.get('round', 0)}轮: {response[:200]}...")

            return {
                "输入信息": {
                    "辩论轮次": len(debate_rounds),
                    "辩论模式": "多轮AI辩论",
                    "参与分析师": ["看涨研究员", "看跌研究员"],
                    "使用AI模型": debate_result.get("ai_model", "未知")
                },
                "输出结果": {
                    "推荐操作": final_decision.get("action", "持有"),
                    "信心度": f"{final_decision.get('confidence', 0.5):.2%}",
                    "推理过程": [final_decision.get("reason", "")],
                    "辩论摘要": {
                        "总交流次数": debate_summary.get("total_exchanges", 0),
                        "看涨发言次数": debate_summary.get("bull_exchanges", 0),
                        "看跌发言次数": debate_summary.get("bear_exchanges", 0),
                        "辩论质量": debate_summary.get("debate_quality", "未知"),
                        "最终发言者": debate_summary.get("final_speaker", ""),
                        "辩论强度对比": {
                            "看涨强度": final_decision.get("bull_strength", 0),
                            "看跌强度": final_decision.get("bear_strength", 0)
                        }
                    },
                    "关键因素": debate_result.get("key_factors", []),
                    "看涨主要观点": bull_arguments,
                    "看跌主要观点": bear_arguments
                }
            }
        except Exception as e:
            self.logger.error(f"格式化辩论详情失败: {e}")
            return None

    def _format_price_targets(self, decision) -> Dict:
        """格式化目标价格信息"""
        price_targets = {}

        if hasattr(decision, 'target_price_short') and decision.target_price_short > 0:
            price_targets["短期目标(0-14天)"] = f"{decision.target_price_short:.2f}元"
        if hasattr(decision, 'target_price_medium') and decision.target_price_medium > 0:
            price_targets["中期目标(15-30天)"] = f"{decision.target_price_medium:.2f}元"
        if hasattr(decision, 'target_price_long') and decision.target_price_long > 0:
            price_targets["长期目标(90天)"] = f"{decision.target_price_long:.2f}元"
        if hasattr(decision, 'upside_potential') and decision.upside_potential != 0:
            price_targets["上涨空间"] = f"{decision.upside_potential:.2%}"
        if hasattr(decision, 'price_range_low') and hasattr(decision, 'price_range_high'):
            if decision.price_range_low > 0 and decision.price_range_high > 0:
                price_targets["价格区间"] = f"{decision.price_range_low:.2f}-{decision.price_range_high:.2f}元"

        return price_targets

    def print_analysis_results(self, results: List[Dict]):
        """
        打印分析结果

        Args:
            results: 分析结果列表
        """
        print("\n" + "="*80)
        print("A股量化交易系统 - TradingAgents多智能体分析结果")
        print("="*80)

        # 统计各种操作建议
        actions = [r["操作建议"] for r in results if r["操作建议"] not in ["错误", "跳过"]]
        skipped_actions = [r for r in results if r["操作建议"] == "跳过"]
        error_actions = [r for r in results if r["操作建议"] == "错误"]

        if actions:
            action_counts = {}
            for action in set(actions):
                action_counts[action] = actions.count(action)

            print(f"\n操作建议统计 (已分析股票):")
            for action, count in action_counts.items():
                percentage = count / len(actions) * 100
                print(f"  {action}: {count} 只股票 ({percentage:.1f}%)")

        if skipped_actions:
            print(f"\n跳过统计: {len(skipped_actions)} 只股票 (价格过高)")
        if error_actions:
            print(f"\n错误统计: {len(error_actions)} 只股票 (分析失败)")

        # 详细结果表格
        print(f"\n详细分析结果:")
        print("-" * 180)
        print(f"{'股票名称':<8} {'代码':<12} {'建议':<6} {'信心度':<8} {'当前价格':<10} {'涨跌幅':<10} {'连续日':<10} {'连续幅度':<12} {'风险':<6} {'决策理由':<30}")
        print("-" * 180)

        for result in results:
            reason = result['决策理由'][:25] + "..." if len(result['决策理由']) > 25 else result['决策理由']
            consecutive_days = result.get('连续涨跌日', 'N/A')
            consecutive_change = result.get('连续涨跌幅度', 'N/A')

            print(f"{result['股票名称']:<8} {result['股票代码']:<12} {result['操作建议']:<6} "
                  f"{result['信心度']:<8} {result['当前价格']:<10} "
                  f"{result['当日涨跌']:<10} {consecutive_days:<10} {consecutive_change:<12} {result['风险等级']:<6} {reason:<30}")

        print("-" * 180)
        print(f"共分析 {len(results)} 只股票，分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def save_results(self, results: List[Dict], output_dir: str = "outputs"):
        """
        保存分析结果到文件

        Args:
            results: 分析结果列表
            output_dir: 输出目录，默认为 "outputs"
        """
        try:
            # 创建时间戳文件夹
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_output_dir = Path(output_dir)
            base_output_dir.mkdir(exist_ok=True)

            # 创建本次分析的专用文件夹
            session_dir = base_output_dir / timestamp
            session_dir.mkdir(exist_ok=True)

            print(f"\n本次分析结果将保存到: {session_dir}")

            # 1. 保存简化版本到CSV（不包含分析师详情）
            csv_results = []
            for result in results:
                csv_result = {k: v for k, v in result.items() if k != "分析师详情"}
                csv_results.append(csv_result)

            df = pd.DataFrame(csv_results)
            csv_filename = session_dir / "analysis_summary.csv"
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"CSV汇总结果: {csv_filename}")

            # 2. 保存完整版本到JSON（包含分析师详情）
            json_filename = session_dir / "analysis_detailed.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"详细JSON结果: {json_filename}")

            # 3. 单独保存分析师详情到专用文件
            analyst_details = []
            for result in results:
                if "分析师详情" in result:
                    analyst_detail = {
                        "股票代码": result["股票代码"],
                        "股票名称": result["股票名称"],
                        "分析时间": result["分析时间"],
                        "分析师详情": result["分析师详情"]
                    }
                    analyst_details.append(analyst_detail)

            if analyst_details:
                analyst_filename = session_dir / "analyst_details.json"
                with open(analyst_filename, 'w', encoding='utf-8') as f:
                    json.dump(analyst_details, f, ensure_ascii=False, indent=2)
                print(f"分析师详情: {analyst_filename}")

                # 生成分析师总结报告
                self.generate_analyst_summary_report(analyst_details, session_dir, timestamp)

            # 4. 保存兼容性JSON（与原格式相同）
            legacy_json_filename = session_dir / "analysis_legacy.json"
            with open(legacy_json_filename, 'w', encoding='utf-8') as f:
                json.dump(csv_results, f, ensure_ascii=False, indent=2)
            print(f"兼容格式JSON: {legacy_json_filename}")

            # 5. 创建本次分析的说明文件
            readme_content = self.generate_session_readme(results, timestamp)
            readme_filename = session_dir / "README.md"
            with open(readme_filename, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            print(f"分析说明文档: {readme_filename}")

            print(f"\n本次分析完成，所有结果已保存到: {session_dir}")
            print(f"文件夹包含: CSV汇总、详细JSON、分析师详情、兼容格式、说明文档")

        except Exception as e:
            print(f"保存结果失败: {e}")
            import traceback
            traceback.print_exc()

    def generate_analyst_summary_report(self, analyst_details: List[Dict], output_dir: Path, timestamp: str):
        """
        生成分析师总结报告

        Args:
            analyst_details: 分析师详情列表
            output_dir: 输出目录
            timestamp: 时间戳
        """
        try:
            summary = {
                "报告标题": "多智能体分析师详细报告",
                "生成时间": timestamp,
                "分析股票数量": len(analyst_details),
                "分析师统计": {}
            }

            # 统计各分析师的推荐情况
            analyst_types = ["基本面分析师", "技术面分析师", "情感面分析师", "AI因子分析师", "多轮辩论分析师"]

            for analyst_type in analyst_types:
                recommendations = {}
                confidences = []

                for detail in analyst_details:
                    analyst_info = detail["分析师详情"].get(analyst_type)
                    if analyst_info:
                        output_result = analyst_info.get("输出结果", {})
                        rec = output_result.get("推荐操作", "N/A")
                        conf_str = output_result.get("信心度", "50.00%")

                        # 统计推荐
                        recommendations[rec] = recommendations.get(rec, 0) + 1

                        # 提取信心度数值
                        try:
                            conf_value = float(conf_str.replace("%", "")) / 100
                            confidences.append(conf_value)
                        except:
                            confidences.append(0.5)

                summary["分析师统计"][analyst_type] = {
                    "推荐分布": recommendations,
                    "平均信心度": f"{np.mean(confidences):.2%}" if confidences else "N/A",
                    "信心度范围": f"{np.min(confidences):.2%} - {np.max(confidences):.2%}" if confidences else "N/A",
                    "参与分析数": len(confidences)
                }

            # 保存总结报告
            summary_filename = output_dir / "analyst_summary_report.json"
            with open(summary_filename, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"分析师总结报告: {summary_filename}")

        except Exception as e:
            print(f"生成分析师总结报告失败: {e}")

    def generate_session_readme(self, results: List[Dict], timestamp: str) -> str:
        """
        生成本次分析会话的README文档

        Args:
            results: 分析结果列表
            timestamp: 时间戳

        Returns:
            README内容字符串
        """
        try:
            # 统计信息
            total_stocks = len(results)
            successful_analyses = sum(1 for r in results if r["操作建议"] not in ["错误", "跳过"])
            action_counts = {}
            for result in results:
                action = result["操作建议"]
                if action not in ["错误", "跳过"]:
                    action_counts[action] = action_counts.get(action, 0) + 1

            # 生成README内容
            readme_content = f"""# 股票分析报告 - {timestamp}

## 📊 分析概览

- **分析时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
- **分析股票数量**: {total_stocks} 只
- **成功分析**: {successful_analyses} 只
- **分析系统**: A股TradingAgents多智能体系统

## 🎯 操作建议分布

"""

            if action_counts:
                for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / successful_analyses) * 100 if successful_analyses > 0 else 0
                    readme_content += f"- **{action}**: {count} 只股票 ({percentage:.1f}%)\n"

            readme_content += f"""

## 📁 文件说明

### 主要结果文件
- `analysis_summary.csv` - 📊 Excel可打开的汇总结果表格
- `analysis_detailed.json` - 📋 包含分析师详情的完整JSON数据
- `analysis_legacy.json` - 🔄 兼容旧版本格式的JSON数据

### 详细分析文件
- `analyst_details.json` - 👥 四个智能分析师的详细分析过程
- `analyst_summary_report.json` - 📊 分析师表现统计报告
- `README.md` - 📄 本分析会话说明文档（当前文件）

## 🤖 智能分析师说明

本次分析使用了四个AI智能分析师：

1. **📊 基本面分析师** - 财务数据、估值分析、行业对比
2. **📈 技术面分析师** - 技术指标、图表形态、趋势分析
3. **📰 情感面分析师** - 新闻舆情、市场情绪、政策影响
4. **🤖 AI因子分析师** - 量化因子、模式识别、智能评分

## 💡 使用建议

1. **快速查看**: 打开 `analysis_summary.csv` 查看所有股票的操作建议
2. **详细分析**: 查看 `analysis_detailed.json` 了解具体分析理由
3. **分析师视角**: 查看 `analyst_details.json` 了解每个分析师的详细观点
4. **Excel分析**: 将CSV文件导入Excel进行进一步的数据分析和筛选

## ⚠️ 免责声明

本分析结果仅供参考，不构成投资建议。投资有风险，决策需谨慎。

---

*本报告由A股TradingAgents智能交易系统自动生成*
"""

            return readme_content

        except Exception as e:
            return f"# 分析报告生成失败\n\n错误信息: {str(e)}"
