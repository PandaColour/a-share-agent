#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析历史"买入"建议的准确性
分析不同信心度区间在接下来5天超过5%涨幅的概率
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

    def get_future_max_gain(self, symbol: str, start_date: str, buy_price: float, days: int = 5) -> Tuple[float, bool]:
        """
        获取未来N天的最高涨幅

        Returns:
            (max_gain, data_valid): 最高涨幅百分比, 数据是否有效
        """
        try:
            # 计算结束日期（开始日期后30天，确保有足够数据）
            start_dt = pd.to_datetime(start_date)
            end_dt = start_dt + timedelta(days=30)
            end_date = end_dt.strftime('%Y-%m-%d')

            # 获取股票数据（只返回DataFrame）
            data = self.data_provider.get_stock_data(
                symbol,
                start_date=start_date,
                end_date=end_date
            )

            if data is None or data.empty:
                return 0.0, False

            # 确保数据按日期排序
            data = data.sort_index()

            # 找到开始日期之后的数据
            future_data = data[data.index > start_dt]

            if len(future_data) < 1:
                return 0.0, False

            # 取接下来N天的数据
            future_data = future_data.head(days)

            # 计算最高涨幅（列名可能是 'high' 或 'High'）
            high_col = 'High' if 'High' in future_data.columns else 'high'
            max_high = future_data[high_col].max()
            max_gain = ((max_high - buy_price) / buy_price) * 100

            return max_gain, True

        except Exception as e:
            print(f"    ⚠️  获取 {symbol} 未来价格失败: {e}")
            return 0.0, False

    def analyze_recommendations(self):
        """分析所有买入建议的表现"""
        print("\n" + "="*80)
        print("🔍 开始分析买入建议的准确性...")
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

            # 获取未来5天的最高涨幅
            max_gain, valid = self.get_future_max_gain(symbol, date, price, days=5)

            if valid:
                exceeds_5pct = max_gain >= 5.0
                result_icon = "✅" if exceeds_5pct else "❌"
                print(f"  {result_icon} 5天最高涨幅: {max_gain:+.2f}%")

                results.append({
                    'symbol': symbol,
                    'name': name,
                    'date': date,
                    'price': price,
                    'confidence': confidence,
                    'max_gain_5d': max_gain,
                    'exceeds_5pct': exceeds_5pct
                })
            else:
                print(f"  ⚠️  无法获取未来数据（可能是最近的建议）")

        print(f"\n✅ 完成分析，有效样本数: {len(results)}")
        return results

    def generate_report(self, results: List[Dict]):
        """生成统计报告"""
        if not results:
            print("\n❌ 没有有效数据进行统计")
            return

        df = pd.DataFrame(results)

        print("\n" + "="*80)
        print("📊 买入建议准确性分析报告")
        print("="*80)

        # 总体统计
        total_count = len(df)
        success_count = df['exceeds_5pct'].sum()
        success_rate = success_count / total_count * 100

        print(f"\n【总体表现】")
        print(f"  样本数量: {total_count}")
        print(f"  成功次数: {success_count} (5天内涨幅≥5%)")
        print(f"  成功率: {success_rate:.2f}%")
        print(f"  平均涨幅: {df['max_gain_5d'].mean():+.2f}%")
        print(f"  最高涨幅: {df['max_gain_5d'].max():+.2f}%")
        print(f"  最低涨幅: {df['max_gain_5d'].min():+.2f}%")

        # 按信心度区间统计
        print(f"\n【按信心度区间分析】")

        confidence_ranges = [
            (0.60, 0.61, "60%-61%"),
            (0.61, 0.62, "61%-62%"),
            (0.62, 0.63, "62%-63%"),
            (0.63, 1.00, ">63%")
        ]

        print(f"\n{'区间':<12} {'样本数':<8} {'成功数':<8} {'成功率':<10} {'平均涨幅':<12} {'最高涨幅':<12}")
        print("-" * 80)

        for low, high, label in confidence_ranges:
            mask = (df['confidence'] >= low) & (df['confidence'] < high)
            subset = df[mask]

            if len(subset) > 0:
                count = len(subset)
                success = subset['exceeds_5pct'].sum()
                rate = success / count * 100
                avg_gain = subset['max_gain_5d'].mean()
                max_gain = subset['max_gain_5d'].max()

                print(f"{label:<12} {count:<8} {success:<8} {rate:>6.2f}%    {avg_gain:>+7.2f}%      {max_gain:>+7.2f}%")
            else:
                print(f"{label:<12} {'0':<8} {'-':<8} {'-':<10} {'-':<12} {'-':<12}")

        # 详细列表（前10个成功案例和前10个失败案例）
        print(f"\n【成功案例 Top 10】（涨幅最高）")
        success_cases = df[df['exceeds_5pct'] == True].nlargest(10, 'max_gain_5d')
        if len(success_cases) > 0:
            print(f"\n{'日期':<12} {'代码':<12} {'名称':<12} {'信心度':<8} {'涨幅':<10}")
            print("-" * 80)
            for _, row in success_cases.iterrows():
                print(f"{row['date']:<12} {row['symbol']:<12} {row['name']:<12} {row['confidence']:>6.1%}  {row['max_gain_5d']:>+7.2f}%")
        else:
            print("  无成功案例")

        print(f"\n【失败案例 Top 10】（跌幅最大）")
        fail_cases = df[df['exceeds_5pct'] == False].nsmallest(10, 'max_gain_5d')
        if len(fail_cases) > 0:
            print(f"\n{'日期':<12} {'代码':<12} {'名称':<12} {'信心度':<8} {'涨幅':<10}")
            print("-" * 80)
            for _, row in fail_cases.iterrows():
                print(f"{row['date']:<12} {row['symbol']:<12} {row['name']:<12} {row['confidence']:>6.1%}  {row['max_gain_5d']:>+7.2f}%")
        else:
            print("  无失败案例")

        # 保存详细结果到CSV
        output_file = "outputs/buy_recommendation_analysis.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 详细结果已保存到: {output_file}")

        print("\n" + "="*80)


def main():
    """主函数"""
    print("="*80)
    print("📊 买入建议准确性分析工具")
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


if __name__ == "__main__":
    main()
