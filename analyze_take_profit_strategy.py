#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析5%止盈策略的持仓天数

策略说明：
- 假设在分析日期按当前价格买入
- 第一天（T+0）不操作
- 从第二天（T+1）开始，每天检查收盘价
- 如果收益率≥5%，立即卖出
- 如果15个交易日内未达到5%，第15天强制卖出
- 统计平均持仓天数、止盈成功率、持仓天数分布等
"""

import os
import sys
import json
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd
import numpy as np

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


class TakeProfitStrategyAnalyzer:
    """5%止盈策略分析器"""

    def __init__(self, outputs_dir: str = "outputs", target_profit: float = 5.0):
        self.outputs_dir = outputs_dir
        self.target_profit = target_profit  # 目标收益率（%）
        self.data_provider = MultiSourceDataProvider()
        self.buy_records = []

    def load_all_analyses(self):
        """加载所有历史分析结果"""
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

                # 提取"买入"建议
                buy_count = 0
                for record in data:
                    if record.get('操作建议') == '买入':
                        record['分析日期'] = analysis_date
                        record['文件路径'] = json_file
                        self.buy_records.append(record)
                        buy_count += 1

                print(f"  📅 {analysis_date}: {buy_count} 个买入建议")

            except Exception as e:
                print(f"❌ 读取文件失败 {json_file}: {e}")

        print(f"\n✅ 总共加载 {len(self.buy_records)} 个买入建议")
        return self.buy_records

    def _parse_date_from_dirname(self, dirname: str) -> str:
        """从目录名解析日期 (格式: YYYYMMDD_HHMMSS)"""
        try:
            date_part = dirname.split('_')[0]
            dt = datetime.strptime(date_part, '%Y%m%d')
            return dt.strftime('%Y-%m-%d')
        except:
            return None

    def _parse_confidence(self, confidence_str: str) -> float:
        """解析信心度字符串 -> 浮点数"""
        try:
            return float(confidence_str.replace('%', '')) / 100
        except:
            return 0.0

    def _parse_price(self, price_str: str) -> float:
        """解析价格字符串 -> 浮点数"""
        try:
            return float(price_str.replace('元', ''))
        except:
            return 0.0

    def analyze_take_profit_strategy(self, symbol: str, start_date: str, buy_price: float) -> Dict:
        """
        分析5%止盈策略的持仓天数

        Returns:
            Dict: {
                'holding_days': int,        # 实际持仓天数
                'sell_price': float,        # 卖出价格
                'return_pct': float,        # 实际收益率
                'hit_target': bool,         # 是否达到目标收益
                'data_valid': bool,         # 数据是否有效
                'daily_returns': List[float]  # 每日收益率序列（用于分析）
            }
        """
        try:
            # 计算结束日期（开始日期后40天，确保有足够数据）
            start_dt = pd.to_datetime(start_date)
            end_dt = start_dt + timedelta(days=40)
            end_date = end_dt.strftime('%Y-%m-%d')

            # 获取股票数据
            data = self.data_provider.get_stock_data(
                symbol,
                start_date=start_date,
                end_date=end_date
            )

            if data is None or data.empty:
                return {'data_valid': False}

            # 确保数据按日期排序
            data = data.sort_index()

            # 找到开始日期之后的数据
            future_data = data[data.index > start_dt]

            if len(future_data) < 2:
                # 数据不足2个交易日
                return {'data_valid': False}

            # 列名处理
            close_col = 'Close' if 'Close' in future_data.columns else 'close'

            # 计算每日收益率
            daily_returns = []
            for i in range(min(15, len(future_data))):
                close_price = future_data.iloc[i][close_col]
                return_pct = ((close_price - buy_price) / buy_price) * 100
                daily_returns.append(return_pct)

            # 策略逻辑：第一天不操作，从第二天开始检查
            holding_days = 1  # 默认至少持有1天
            sell_price = buy_price
            return_pct = 0.0
            hit_target = False

            # 从第2天（索引1）开始检查
            for day_idx in range(1, min(15, len(future_data))):
                close_price = future_data.iloc[day_idx][close_col]
                current_return = ((close_price - buy_price) / buy_price) * 100

                if current_return >= self.target_profit:
                    # 达到目标收益，卖出
                    holding_days = day_idx + 1  # 天数从1开始计
                    sell_price = close_price
                    return_pct = current_return
                    hit_target = True
                    break

            # 如果未达到目标，则在第15天（或最后一天）卖出
            if not hit_target:
                last_idx = min(14, len(future_data) - 1)
                holding_days = last_idx + 1
                sell_price = future_data.iloc[last_idx][close_col]
                return_pct = ((sell_price - buy_price) / buy_price) * 100

            return {
                'holding_days': holding_days,
                'sell_price': sell_price,
                'return_pct': return_pct,
                'hit_target': hit_target,
                'data_valid': True,
                'daily_returns': daily_returns
            }

        except Exception as e:
            print(f"    ⚠️  分析 {symbol} 止盈策略失败: {e}")
            return {'data_valid': False}

    def analyze_all_recommendations(self):
        """分析所有买入建议的止盈策略表现"""
        print("\n" + "="*80)
        print(f"🔍 开始分析{self.target_profit}%止盈策略...")
        print("="*80)

        results = []

        for i, record in enumerate(self.buy_records, 1):
            symbol = record['股票代码']
            name = record['股票名称']
            date = record['分析日期']
            confidence = self._parse_confidence(record['信心度'])
            price = self._parse_price(record['当前价格'])

            print(f"\n[{i}/{len(self.buy_records)}] {name}({symbol}) - {date}")
            print(f"  买入价: ¥{price:.2f}, 信心度: {confidence:.1%}")

            # 分析止盈策略
            strategy_result = self.analyze_take_profit_strategy(symbol, date, price)

            if strategy_result.get('data_valid'):
                holding_days = strategy_result['holding_days']
                return_pct = strategy_result['return_pct']
                hit_target = strategy_result['hit_target']

                result_icon = "🎯" if hit_target else "⏰"
                status = f"第{holding_days}天止盈" if hit_target else f"第{holding_days}天到期"

                print(f"  {result_icon} {status}: {return_pct:+.2f}%")

                results.append({
                    'symbol': symbol,
                    'name': name,
                    'date': date,
                    'buy_price': price,
                    'confidence': confidence,
                    'holding_days': holding_days,
                    'sell_price': strategy_result['sell_price'],
                    'return_pct': return_pct,
                    'hit_target': hit_target,
                    'daily_returns': strategy_result['daily_returns']
                })
            else:
                print(f"  ⚠️  无法获取未来数据（可能是最近的建议或数据不足）")

        print(f"\n✅ 完成分析，有效样本数: {len(results)}")
        return results

    def generate_report(self, results: List[Dict]):
        """生成统计报告"""
        if not results:
            print("\n❌ 没有有效数据进行统计")
            return

        df = pd.DataFrame(results)

        print("\n" + "="*80)
        print(f"📊 {self.target_profit}%止盈策略分析报告")
        print("="*80)

        # 总体统计
        total_count = len(df)
        hit_target_count = df['hit_target'].sum()
        hit_target_rate = hit_target_count / total_count * 100

        avg_holding_days = df['holding_days'].mean()
        median_holding_days = df['holding_days'].median()
        min_holding_days = df['holding_days'].min()
        max_holding_days = df['holding_days'].max()

        avg_return = df['return_pct'].mean()
        median_return = df['return_pct'].median()

        # 只统计达到目标的样本
        hit_target_df = df[df['hit_target'] == True]
        if len(hit_target_df) > 0:
            avg_days_when_hit = hit_target_df['holding_days'].mean()
            median_days_when_hit = hit_target_df['holding_days'].median()
        else:
            avg_days_when_hit = 0
            median_days_when_hit = 0

        print(f"\n【总体表现】")
        print(f"  样本数量: {total_count}")
        print(f"  止盈成功次数: {hit_target_count}")
        print(f"  止盈成功率: {hit_target_rate:.2f}% (达到{self.target_profit}%目标的比例)")
        print(f"  平均持仓天数: {avg_holding_days:.2f}天")
        print(f"  中位数持仓天数: {median_holding_days:.0f}天")
        print(f"  持仓天数范围: {min_holding_days}天 - {max_holding_days}天")
        print(f"  平均收益率: {avg_return:+.2f}%")
        print(f"  中位数收益率: {median_return:+.2f}%")

        if hit_target_count > 0:
            print(f"\n【止盈成功时的持仓天数】")
            print(f"  平均持仓天数: {avg_days_when_hit:.2f}天")
            print(f"  中位数持仓天数: {median_days_when_hit:.0f}天")

        # 持仓天数分布
        print(f"\n【持仓天数分布】")
        print(f"\n{'持仓天数':<12} {'数量':<8} {'占比':<10} {'止盈数':<10} {'止盈率':<10}")
        print("-" * 60)

        for days in range(1, 16):
            day_mask = df['holding_days'] == days
            day_count = day_mask.sum()
            if day_count > 0:
                day_percentage = day_count / total_count * 100
                day_hit_count = df[day_mask & (df['hit_target'] == True)].shape[0]
                day_hit_rate = day_hit_count / day_count * 100
                print(f"{days}天{'':<10} {day_count:<8} {day_percentage:>6.2f}%    {day_hit_count:<10} {day_hit_rate:>6.2f}%")

        # 按信心度区间统计
        print(f"\n【按信心度区间分析】")

        confidence_ranges = [
            (0.60, 0.61, "60%-61%"),
            (0.61, 0.62, "61%-62%"),
            (0.62, 0.63, "62%-63%"),
            (0.63, 1.00, ">63%")
        ]

        print(f"\n{'信心度区间':<12} {'样本数':<8} {'止盈数':<8} {'止盈率':<10} {'平均持仓':<12} {'平均收益':<12}")
        print("-" * 80)

        for low, high, label in confidence_ranges:
            mask = (df['confidence'] >= low) & (df['confidence'] < high)
            subset = df[mask]

            if len(subset) > 0:
                count = len(subset)
                hit_count = subset['hit_target'].sum()
                hit_rate = hit_count / count * 100
                avg_days = subset['holding_days'].mean()
                avg_ret = subset['return_pct'].mean()

                print(f"{label:<12} {count:<8} {hit_count:<8} {hit_rate:>6.2f}%    {avg_days:>7.2f}天     {avg_ret:>+7.2f}%")
            else:
                print(f"{label:<12} {'0':<8} {'-':<8} {'-':<10} {'-':<12} {'-':<12}")

        # 最快止盈案例
        print(f"\n【最快止盈 Top 10】（达到{self.target_profit}%目标且持仓天数最短）")
        fastest_hits = df[df['hit_target'] == True].nsmallest(10, 'holding_days')
        if len(fastest_hits) > 0:
            print(f"\n{'日期':<12} {'代码':<12} {'名称':<12} {'持仓天数':<10} {'收益率':<10} {'信心度':<8}")
            print("-" * 85)
            for _, row in fastest_hits.iterrows():
                print(f"{row['date']:<12} {row['symbol']:<12} {row['name']:<12} "
                      f"{row['holding_days']}天{'':<7} {row['return_pct']:>+7.2f}%    {row['confidence']:>6.1%}")
        else:
            print("  无案例")

        # 未止盈但收益最好的案例
        print(f"\n【未止盈但收益最高 Top 10】（未达到{self.target_profit}%但收益最好）")
        best_non_hits = df[df['hit_target'] == False].nlargest(10, 'return_pct')
        if len(best_non_hits) > 0:
            print(f"\n{'日期':<12} {'代码':<12} {'名称':<12} {'持仓天数':<10} {'收益率':<10} {'信心度':<8}")
            print("-" * 85)
            for _, row in best_non_hits.iterrows():
                print(f"{row['date']:<12} {row['symbol']:<12} {row['name']:<12} "
                      f"{row['holding_days']}天{'':<7} {row['return_pct']:>+7.2f}%    {row['confidence']:>6.1%}")
        else:
            print("  无案例")

        # 保存详细结果到CSV
        output_file = f"outputs/take_profit_{self.target_profit:.0f}pct_analysis.csv"
        df_save = df.drop(columns=['daily_returns'])  # 删除列表类型的列
        df_save.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 详细结果已保存到: {output_file}")

        print("\n" + "="*80)


def main():
    """主函数"""
    print("="*80)
    print("📊 5%止盈策略分析工具")
    print("="*80)

    # 可以修改目标收益率
    target_profit = 5.0  # 目标收益率（%）

    analyzer = TakeProfitStrategyAnalyzer(target_profit=target_profit)

    # 1. 加载所有历史分析
    analyzer.load_all_analyses()

    if not analyzer.buy_records:
        print("\n❌ 没有找到买入建议记录")
        return

    # 2. 分析每个建议的止盈策略表现
    results = analyzer.analyze_all_recommendations()

    # 3. 生成统计报告
    analyzer.generate_report(results)

    print("\n✅ 分析完成！")
    print("\n📝 策略说明:")
    print(f"  - 假设在分析当日收盘价买入")
    print(f"  - 第一天（T+0）不操作")
    print(f"  - 从第二天（T+1）开始，每天检查收盘价")
    print(f"  - 如果收益率≥{target_profit}%，立即卖出")
    print(f"  - 如果15个交易日内未达到{target_profit}%，第15天强制卖出")
    print(f"  - 统计持仓天数分布、止盈成功率等指标")


if __name__ == "__main__":
    main()
