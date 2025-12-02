#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术面分析师和AI因子分析师的信号策略准确度分析

策略说明：
- 当技术面分析师或AI因子分析师给出"买入"信号时买入
- 卖出条件（满足任一即卖出）：
  1. 收益率达到5%
  2. 持股超过15天
  3. 出现"卖出"信号

分析维度：
- 止盈成功率
- 平均持仓天数
- 平均收益率
- 卖出信号的有效性
"""

import os
import sys
import json
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np
from collections import defaultdict

# 设置控制台编码
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# 禁用并行功能
os.environ['LOKY_MAX_CPU_COUNT'] = '1'
os.environ['JOBLIB_MULTIPROCESSING'] = '0'

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.data.multi_source_data_provider import MultiSourceDataProvider


class AnalystSignalStrategyAnalyzer:
    """分析师信号策略分析器"""

    def __init__(self, outputs_dir: str = "outputs", target_profit: float = 5.0, max_holding_days: int = 15):
        self.outputs_dir = outputs_dir
        self.target_profit = target_profit  # 目标收益率（%）
        self.max_holding_days = max_holding_days  # 最大持仓天数
        self.data_provider = MultiSourceDataProvider()

        # 存储所有分析结果，按日期索引
        self.all_analyses = {}  # {date: [{record1}, {record2}, ...]}
        self.date_list = []  # 排序的日期列表

        # 存储分析师的交易记录
        self.analyst_trades = {
            'technical': [],  # 技术面分析师
            'ai_factor': []   # AI因子分析师
        }

    def load_all_analyses(self):
        """加载所有历史分析结果并按日期索引"""
        print(f"\n📂 扫描 {self.outputs_dir} 目录...")

        # 查找所有 analysis_detailed.json 文件
        pattern = os.path.join(self.outputs_dir, "*/analysis_detailed.json")
        json_files = glob.glob(pattern)

        print(f"找到 {len(json_files)} 个分析文件")

        for json_file in json_files:
            try:
                # 从目录名提取日期
                dir_name = os.path.basename(os.path.dirname(json_file))
                analysis_date = self._parse_date_from_dirname(dir_name)

                if not analysis_date:
                    print(f"⚠️  无法解析日期: {dir_name}")
                    continue

                # 读取JSON文件
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 按日期存储
                self.all_analyses[analysis_date] = data
                print(f"  📅 {analysis_date}: {len(data)} 条记录")

            except Exception as e:
                print(f"❌ 读取文件失败 {json_file}: {e}")

        # 排序日期列表
        self.date_list = sorted(self.all_analyses.keys())
        print(f"\n✅ 总共加载 {len(self.date_list)} 个分析日期")
        print(f"   日期范围: {self.date_list[0]} 到 {self.date_list[-1]}")

        return len(self.date_list)

    def _parse_date_from_dirname(self, dirname: str) -> str:
        """从目录名解析日期 (格式: YYYYMMDD_HHMMSS)"""
        try:
            date_part = dirname.split('_')[0]
            dt = datetime.strptime(date_part, '%Y%m%d')
            return dt.strftime('%Y-%m-%d')
        except:
            return None

    def _parse_price(self, price_str: str) -> float:
        """解析价格字符串 -> 浮点数"""
        try:
            return float(price_str.replace('元', ''))
        except:
            return 0.0

    def _parse_confidence(self, confidence_str: str) -> float:
        """解析信心度字符串 -> 浮点数"""
        try:
            return float(confidence_str.replace('%', '')) / 100
        except:
            return 0.0

    def extract_buy_signals(self):
        """提取技术面和AI因子分析师的买入信号"""
        print("\n🔍 提取分析师买入信号...")

        buy_signals = {
            'technical': [],
            'ai_factor': []
        }

        for date in self.date_list:
            records = self.all_analyses[date]

            for record in records:
                symbol = record['股票代码']
                name = record['股票名称']
                price = self._parse_price(record['当前价格'])

                analyst_details = record.get('分析师详情', {})

                # 技术面分析师
                technical = analyst_details.get('技术面分析师', {}).get('输出结果', {})
                tech_recommendation = technical.get('推荐操作', '未知')
                tech_confidence = self._parse_confidence(technical.get('信心度', '0%'))

                if tech_recommendation == '买入':
                    buy_signals['technical'].append({
                        'buy_date': date,
                        'symbol': symbol,
                        'name': name,
                        'buy_price': price,
                        'confidence': tech_confidence,
                        'record': record
                    })

                # AI因子分析师
                ai_factor = analyst_details.get('AI因子分析师', {}).get('输出结果', {})
                ai_recommendation = ai_factor.get('推荐操作', '未知')
                ai_confidence = self._parse_confidence(ai_factor.get('信心度', '0%'))

                if ai_recommendation == '买入':
                    buy_signals['ai_factor'].append({
                        'buy_date': date,
                        'symbol': symbol,
                        'name': name,
                        'buy_price': price,
                        'confidence': ai_confidence,
                        'record': record
                    })

        print(f"  技术面分析师买入信号: {len(buy_signals['technical'])} 个")
        print(f"  AI因子分析师买入信号: {len(buy_signals['ai_factor'])} 个")

        return buy_signals

    def check_sell_signal(self, symbol: str, analyst_type: str, check_date: str) -> bool:
        """检查特定日期是否出现卖出信号"""
        if check_date not in self.all_analyses:
            return False

        records = self.all_analyses[check_date]

        for record in records:
            if record['股票代码'] == symbol:
                analyst_details = record.get('分析师详情', {})

                if analyst_type == 'technical':
                    technical = analyst_details.get('技术面分析师', {}).get('输出结果', {})
                    recommendation = technical.get('推荐操作', '未知')
                elif analyst_type == 'ai_factor':
                    ai_factor = analyst_details.get('AI因子分析师', {}).get('输出结果', {})
                    recommendation = ai_factor.get('推荐操作', '未知')
                else:
                    return False

                return recommendation == '卖出'

        return False

    def analyze_signal_strategy(self, buy_signal: Dict, analyst_type: str) -> Optional[Dict]:
        """
        分析单个买入信号的策略表现

        卖出条件（满足任一即卖出）：
        1. 收益率达到5%
        2. 持股超过15天
        3. 出现卖出信号
        """
        symbol = buy_signal['symbol']
        buy_date = buy_signal['buy_date']
        buy_price = buy_signal['buy_price']

        try:
            # 获取股票数据
            start_dt = pd.to_datetime(buy_date)
            end_dt = start_dt + timedelta(days=40)

            data = self.data_provider.get_stock_data(
                symbol,
                start_date=buy_date,
                end_date=end_dt.strftime('%Y-%m-%d')
            )

            if data is None or data.empty:
                return None

            # 确保数据按日期排序
            data = data.sort_index()
            future_data = data[data.index > start_dt]

            if len(future_data) < 2:
                return None

            # 列名处理
            close_col = 'Close' if 'Close' in future_data.columns else 'close'

            # 策略逻辑：从第二天开始检查
            holding_days = 1
            sell_price = buy_price
            return_pct = 0.0
            sell_reason = 'unknown'
            hit_target = False

            # 获取后续日期，用于检查卖出信号
            future_dates = []
            for i in range(min(self.max_holding_days, len(future_data))):
                future_dt = future_data.index[i]
                future_date_str = future_dt.strftime('%Y-%m-%d')
                future_dates.append(future_date_str)

            # 从第2天开始检查
            for day_idx in range(1, min(self.max_holding_days, len(future_data))):
                close_price = future_data.iloc[day_idx][close_col]
                current_return = ((close_price - buy_price) / buy_price) * 100
                check_date = future_dates[day_idx]

                # 条件1: 收益率达到5%
                if current_return >= self.target_profit:
                    holding_days = day_idx + 1
                    sell_price = close_price
                    return_pct = current_return
                    sell_reason = 'take_profit'
                    hit_target = True
                    break

                # 条件3: 出现卖出信号
                if self.check_sell_signal(symbol, analyst_type, check_date):
                    holding_days = day_idx + 1
                    sell_price = close_price
                    return_pct = current_return
                    sell_reason = 'sell_signal'
                    break

            # 条件2: 持股超过15天（如果未满足其他条件）
            if sell_reason == 'unknown':
                last_idx = min(self.max_holding_days - 1, len(future_data) - 1)
                holding_days = last_idx + 1
                sell_price = future_data.iloc[last_idx][close_col]
                return_pct = ((sell_price - buy_price) / buy_price) * 100
                sell_reason = 'max_holding_days'

            return {
                'symbol': symbol,
                'name': buy_signal['name'],
                'buy_date': buy_date,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'holding_days': holding_days,
                'return_pct': return_pct,
                'sell_reason': sell_reason,
                'hit_target': hit_target,
                'confidence': buy_signal['confidence']
            }

        except Exception as e:
            print(f"    ⚠️  分析 {symbol} 策略失败: {e}")
            return None

    def analyze_all_signals(self, buy_signals: Dict):
        """分析所有买入信号的策略表现"""
        print("\n" + "="*80)
        print("🔍 开始分析分析师信号策略...")
        print("="*80)

        results = {
            'technical': [],
            'ai_factor': []
        }

        # 分析技术面分析师
        print(f"\n【技术面分析师】分析 {len(buy_signals['technical'])} 个买入信号")
        for i, signal in enumerate(buy_signals['technical'], 1):
            print(f"  [{i}/{len(buy_signals['technical'])}] {signal['name']}({signal['symbol']}) @ {signal['buy_date']}")

            result = self.analyze_signal_strategy(signal, 'technical')
            if result:
                results['technical'].append(result)

                reason_map = {
                    'take_profit': '🎯 止盈',
                    'sell_signal': '📉 卖出信号',
                    'max_holding_days': '⏰ 到期'
                }
                print(f"      {reason_map.get(result['sell_reason'], '❓')} 第{result['holding_days']}天: {result['return_pct']:+.2f}%")

        # 分析AI因子分析师
        print(f"\n【AI因子分析师】分析 {len(buy_signals['ai_factor'])} 个买入信号")
        for i, signal in enumerate(buy_signals['ai_factor'], 1):
            print(f"  [{i}/{len(buy_signals['ai_factor'])}] {signal['name']}({signal['symbol']}) @ {signal['buy_date']}")

            result = self.analyze_signal_strategy(signal, 'ai_factor')
            if result:
                results['ai_factor'].append(result)

                reason_map = {
                    'take_profit': '🎯 止盈',
                    'sell_signal': '📉 卖出信号',
                    'max_holding_days': '⏰ 到期'
                }
                print(f"      {reason_map.get(result['sell_reason'], '❓')} 第{result['holding_days']}天: {result['return_pct']:+.2f}%")

        print(f"\n✅ 分析完成")
        print(f"  技术面分析师有效样本: {len(results['technical'])}")
        print(f"  AI因子分析师有效样本: {len(results['ai_factor'])}")

        return results

    def generate_report(self, results: Dict):
        """生成详细分析报告"""
        print("\n" + "="*100)
        print("📊 分析师信号策略准确度报告")
        print("="*100)

        for analyst_type, analyst_name in [('technical', '技术面分析师'), ('ai_factor', 'AI因子分析师')]:
            data = results[analyst_type]

            if not data:
                print(f"\n【{analyst_name}】")
                print("  ⚠️  无有效数据")
                continue

            df = pd.DataFrame(data)

            print(f"\n{'='*100}")
            print(f"【{analyst_name}】")
            print('='*100)

            # 总体统计
            total_count = len(df)
            hit_target_count = df['hit_target'].sum()
            hit_target_rate = hit_target_count / total_count * 100

            avg_return = df['return_pct'].mean()
            median_return = df['return_pct'].median()
            avg_holding_days = df['holding_days'].mean()

            print(f"\n【总体表现】")
            print(f"  总交易次数: {total_count}")
            print(f"  止盈成功次数: {hit_target_count}")
            print(f"  止盈成功率: {hit_target_rate:.2f}%")
            print(f"  平均收益率: {avg_return:+.2f}%")
            print(f"  中位数收益率: {median_return:+.2f}%")
            print(f"  平均持仓天数: {avg_holding_days:.2f}天")

            # 按卖出原因统计
            print(f"\n【卖出原因分布】")
            sell_reason_stats = df['sell_reason'].value_counts()

            reason_map = {
                'take_profit': '止盈(收益≥5%)',
                'sell_signal': '卖出信号',
                'max_holding_days': '到期(15天)'
            }

            for reason, count in sell_reason_stats.items():
                subset = df[df['sell_reason'] == reason]
                avg_ret = subset['return_pct'].mean()
                avg_days = subset['holding_days'].mean()

                print(f"  {reason_map.get(reason, reason)}: {count}次 ({count/total_count*100:.1f}%) "
                      f"- 平均收益{avg_ret:+.2f}%, 平均{avg_days:.1f}天")

            # 卖出信号有效性分析
            sell_signal_df = df[df['sell_reason'] == 'sell_signal']
            if len(sell_signal_df) > 0:
                print(f"\n【卖出信号有效性】")
                positive_count = (sell_signal_df['return_pct'] > 0).sum()
                negative_count = (sell_signal_df['return_pct'] < 0).sum()

                print(f"  卖出信号触发次数: {len(sell_signal_df)}")
                print(f"  盈利卖出: {positive_count}次 ({positive_count/len(sell_signal_df)*100:.1f}%)")
                print(f"  亏损卖出: {negative_count}次 ({negative_count/len(sell_signal_df)*100:.1f}%)")
                print(f"  平均收益: {sell_signal_df['return_pct'].mean():+.2f}%")

            # Top 10 最佳交易
            print(f"\n【最佳交易 Top 10】")
            top_trades = df.nlargest(10, 'return_pct')
            print(f"\n{'日期':<12} {'代码':<12} {'名称':<10} {'持仓天数':<10} {'收益率':<10} {'卖出原因':<15}")
            print("-" * 90)

            for _, row in top_trades.iterrows():
                reason = reason_map.get(row['sell_reason'], row['sell_reason'])
                print(f"{row['buy_date']:<12} {row['symbol']:<12} {row['name']:<10} "
                      f"{row['holding_days']}天{'':<7} {row['return_pct']:>+7.2f}%    {reason:<15}")

            # 最差交易
            print(f"\n【最差交易 Top 10】")
            worst_trades = df.nsmallest(10, 'return_pct')
            print(f"\n{'日期':<12} {'代码':<12} {'名称':<10} {'持仓天数':<10} {'收益率':<10} {'卖出原因':<15}")
            print("-" * 90)

            for _, row in worst_trades.iterrows():
                reason = reason_map.get(row['sell_reason'], row['sell_reason'])
                print(f"{row['buy_date']:<12} {row['symbol']:<12} {row['name']:<10} "
                      f"{row['holding_days']}天{'':<7} {row['return_pct']:>+7.2f}%    {reason:<15}")

            # 保存详细结果
            output_file = f"outputs/{analyst_type}_signal_strategy_analysis.csv"
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"\n💾 详细结果已保存到: {output_file}")

        # 对比分析
        if results['technical'] and results['ai_factor']:
            print("\n" + "="*100)
            print("📊 技术面 vs AI因子 对比分析")
            print("="*100)

            tech_df = pd.DataFrame(results['technical'])
            ai_df = pd.DataFrame(results['ai_factor'])

            print(f"\n{'指标':<20} {'技术面分析师':<20} {'AI因子分析师':<20}")
            print("-" * 60)
            print(f"{'样本数':<20} {len(tech_df):<20} {len(ai_df):<20}")
            print(f"{'止盈成功率':<20} {tech_df['hit_target'].mean()*100:>6.2f}%{'':<13} {ai_df['hit_target'].mean()*100:>6.2f}%")
            print(f"{'平均收益率':<20} {tech_df['return_pct'].mean():>+7.2f}%{'':<12} {ai_df['return_pct'].mean():>+7.2f}%")
            print(f"{'中位数收益率':<20} {tech_df['return_pct'].median():>+7.2f}%{'':<12} {ai_df['return_pct'].median():>+7.2f}%")
            print(f"{'平均持仓天数':<20} {tech_df['holding_days'].mean():>7.2f}天{'':<11} {ai_df['holding_days'].mean():>7.2f}天")

        print("\n" + "="*100)


def main():
    """主函数"""
    print("="*100)
    print("📊 技术面 & AI因子分析师信号策略准确度分析工具")
    print("="*100)

    analyzer = AnalystSignalStrategyAnalyzer(target_profit=5.0, max_holding_days=15)

    # 1. 加载所有历史分析
    if analyzer.load_all_analyses() == 0:
        print("\n❌ 没有找到分析记录")
        return

    # 2. 提取买入信号
    buy_signals = analyzer.extract_buy_signals()

    if not buy_signals['technical'] and not buy_signals['ai_factor']:
        print("\n❌ 没有找到买入信号")
        return

    # 3. 分析所有信号的策略表现
    results = analyzer.analyze_all_signals(buy_signals)

    # 4. 生成详细报告
    analyzer.generate_report(results)

    print("\n✅ 分析完成！")
    print("\n📝 策略说明:")
    print(f"  - 买入条件: 技术面分析师或AI因子分析师给出'买入'信号")
    print(f"  - 卖出条件（满足任一即卖出）:")
    print(f"    1. 收益率达到5%")
    print(f"    2. 持股超过15天")
    print(f"    3. 出现'卖出'信号")


if __name__ == "__main__":
    main()
