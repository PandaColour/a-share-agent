#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析历史"买入"建议的准确性

策略说明：
- 假设在分析日期按当前价格买入
- 持有15个交易日后卖出（第15个交易日收盘价）
- 统计盈利比例（收益>0的比例）
- 统计收益率分布、平均收益、最高/最低收益等
- 按信心度区间分析不同置信水平的表现
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


class BuyRecommendationAnalyzer:
    """买入建议准确性分析器"""

    def __init__(self, outputs_dir: str = "outputs"):
        self.outputs_dir = outputs_dir
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

    def get_15day_return(self, symbol: str, start_date: str, buy_price: float) -> Tuple[float, float, bool]:
        """
        获取买入后15个交易日的收益率和最高涨幅

        Returns:
            (return_15d, max_gain_15d, data_valid): 15日收益率, 15日内最高涨幅, 数据是否有效
        """
        try:
            # 计算结束日期（开始日期后40天，确保有足够数据）
            start_dt = pd.to_datetime(start_date)
            end_dt = start_dt + timedelta(days=40)
            end_date = end_dt.strftime('%Y-%m-%d')

            # 获取股票数据（只返回DataFrame）
            data = self.data_provider.get_stock_data(
                symbol,
                start_date=start_date,
                end_date=end_date
            )

            if data is None or data.empty:
                return 0.0, 0.0, False

            # 确保数据按日期排序
            data = data.sort_index()

            # 找到开始日期之后的数据
            future_data = data[data.index > start_dt]

            if len(future_data) < 15:
                # 数据不足15个交易日
                return 0.0, 0.0, False

            # 取接下来15个交易日的数据
            future_15d = future_data.head(15)

            # 获取第15天的收盘价（列名可能是 'close' 或 'Close'）
            close_col = 'Close' if 'Close' in future_15d.columns else 'close'
            sell_price = future_15d.iloc[14][close_col]  # 第15个交易日的收盘价

            # 计算15日收益率
            return_15d = ((sell_price - buy_price) / buy_price) * 100

            # 计算15日内最高涨幅
            high_col = 'High' if 'High' in future_15d.columns else 'high'
            max_high = future_15d[high_col].max()
            max_gain_15d = ((max_high - buy_price) / buy_price) * 100

            return return_15d, max_gain_15d, True

        except Exception as e:
            print(f"    ⚠️  获取 {symbol} 未来价格失败: {e}")
            return 0.0, 0.0, False

    def analyze_recommendations(self):
        """分析所有买入建议的表现"""
        print("\n" + "="*80)
        print("🔍 开始分析买入建议的准确性（15个交易日持仓）...")
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

            # 获取15个交易日的收益率和最高涨幅
            return_15d, max_gain_15d, valid = self.get_15day_return(symbol, date, price)

            if valid:
                is_profitable = return_15d > 0
                result_icon = "✅" if is_profitable else "❌"
                print(f"  {result_icon} 15日收益: {return_15d:+.2f}% | 期间最高: {max_gain_15d:+.2f}%")

                results.append({
                    'symbol': symbol,
                    'name': name,
                    'date': date,
                    'price': price,
                    'confidence': confidence,
                    'return_15d': return_15d,
                    'max_gain_15d': max_gain_15d,
                    'is_profitable': is_profitable
                })
            else:
                print(f"  ⚠️  无法获取未来数据（可能是最近的建议或数据不足15个交易日）")

        print(f"\n✅ 完成分析，有效样本数: {len(results)}")
        return results

    def generate_report(self, results: List[Dict]):
        """生成统计报告"""
        if not results:
            print("\n❌ 没有有效数据进行统计")
            return

        df = pd.DataFrame(results)

        print("\n" + "="*80)
        print("📊 买入建议准确性分析报告（15个交易日持仓）")
        print("="*80)

        # 总体统计
        total_count = len(df)
        profitable_count = df['is_profitable'].sum()
        profitable_rate = profitable_count / total_count * 100

        avg_return = df['return_15d'].mean()
        median_return = df['return_15d'].median()
        max_return = df['return_15d'].max()
        min_return = df['return_15d'].min()
        std_return = df['return_15d'].std()

        print(f"\n【总体表现】")
        print(f"  样本数量: {total_count}")
        print(f"  盈利次数: {profitable_count}")
        print(f"  盈利比例: {profitable_rate:.2f}% (15日后收益>0的比例)")
        print(f"  平均收益率: {avg_return:+.2f}%")
        print(f"  中位数收益率: {median_return:+.2f}%")
        print(f"  最高收益率: {max_return:+.2f}%")
        print(f"  最低收益率: {min_return:+.2f}%")
        print(f"  收益率标准差: {std_return:.2f}%")

        # 收益率分布统计
        print(f"\n【收益率分布】")
        gain_ranges = [
            (10, float('inf'), "涨幅>10%"),
            (5, 10, "涨幅5%-10%"),
            (0, 5, "涨幅0%-5%"),
            (-5, 0, "跌幅0%-5%"),
            (-10, -5, "跌幅5%-10%"),
            (float('-inf'), -10, "跌幅>10%")
        ]

        print(f"\n{'收益区间':<15} {'数量':<8} {'占比':<10}")
        print("-" * 40)
        for low, high, label in gain_ranges:
            if high == float('inf'):
                mask = df['return_15d'] >= low
            elif low == float('-inf'):
                mask = df['return_15d'] < high
            else:
                mask = (df['return_15d'] >= low) & (df['return_15d'] < high)

            count = mask.sum()
            percentage = count / total_count * 100
            print(f"{label:<15} {count:<8} {percentage:>6.2f}%")

        # 按信心度区间统计
        print(f"\n【按信心度区间分析】")

        confidence_ranges = [
            (0.60, 0.61, "60%-61%"),
            (0.61, 0.62, "61%-62%"),
            (0.62, 0.63, "62%-63%"),
            (0.63, 1.00, ">63%")
        ]

        print(f"\n{'信心度区间':<12} {'样本数':<8} {'盈利数':<8} {'盈利率':<10} {'平均收益':<12} {'最高收益':<12}")
        print("-" * 80)

        for low, high, label in confidence_ranges:
            mask = (df['confidence'] >= low) & (df['confidence'] < high)
            subset = df[mask]

            if len(subset) > 0:
                count = len(subset)
                profitable = subset['is_profitable'].sum()
                rate = profitable / count * 100
                avg_return = subset['return_15d'].mean()
                max_return = subset['return_15d'].max()

                print(f"{label:<12} {count:<8} {profitable:<8} {rate:>6.2f}%    {avg_return:>+7.2f}%      {max_return:>+7.2f}%")
            else:
                print(f"{label:<12} {'0':<8} {'-':<8} {'-':<10} {'-':<12} {'-':<12}")

        # 详细列表（前10个最佳和最差案例）
        print(f"\n【最佳案例 Top 10】（收益率最高）")
        best_cases = df.nlargest(10, 'return_15d')
        if len(best_cases) > 0:
            print(f"\n{'日期':<12} {'代码':<12} {'名称':<12} {'信心度':<8} {'15日收益':<10} {'期间最高':<10}")
            print("-" * 85)
            for _, row in best_cases.iterrows():
                print(f"{row['date']:<12} {row['symbol']:<12} {row['name']:<12} "
                      f"{row['confidence']:>6.1%}  {row['return_15d']:>+7.2f}%    {row['max_gain_15d']:>+7.2f}%")
        else:
            print("  无案例")

        print(f"\n【最差案例 Top 10】（亏损最大）")
        worst_cases = df.nsmallest(10, 'return_15d')
        if len(worst_cases) > 0:
            print(f"\n{'日期':<12} {'代码':<12} {'名称':<12} {'信心度':<8} {'15日收益':<10} {'期间最高':<10}")
            print("-" * 85)
            for _, row in worst_cases.iterrows():
                print(f"{row['date']:<12} {row['symbol']:<12} {row['name']:<12} "
                      f"{row['confidence']:>6.1%}  {row['return_15d']:>+7.2f}%    {row['max_gain_15d']:>+7.2f}%")
        else:
            print("  无案例")

        # 保存详细结果到CSV
        output_file = "outputs/buy_recommendation_analysis_15d.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 详细结果已保存到: {output_file}")

        print("\n" + "="*80)


def main():
    """主函数"""
    print("="*80)
    print("📊 买入建议准确性分析工具（15个交易日持仓策略）")
    print("="*80)

    analyzer = BuyRecommendationAnalyzer()

    # 1. 加载所有历史分析
    analyzer.load_all_analyses()

    if not analyzer.buy_records:
        print("\n❌ 没有找到买入建议记录")
        return

    # 2. 分析每个建议的表现
    results = analyzer.analyze_recommendations()

    # 3. 生成统计报告
    analyzer.generate_report(results)

    print("\n✅ 分析完成！")
    print("\n📝 分析说明:")
    print("  - 假设在分析当日收盘价买入")
    print("  - 持有15个交易日后卖出（第15个交易日收盘价）")
    print("  - 统计实际收益率和盈利概率")
    print("  - 同时记录持仓期间的最高涨幅（作为参考）")


if __name__ == "__main__":
    main()
