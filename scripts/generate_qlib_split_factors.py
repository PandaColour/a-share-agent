# -*- coding: utf-8 -*-
"""
Qlib因子拆分代码生成器

自动生成97个独立的Qlib因子类，分为5个类别文件：
- qlib_momentum_factors.py (23个)
- qlib_volatility_factors.py (20个)
- qlib_volprice_factors.py (17个)
- qlib_technical_factors.py (19个)
- qlib_trend_factors.py (18个)
"""

import os
from typing import List, Tuple
from pathlib import Path


# 因子定义：(name_suffix, expression, description)
FACTOR_DEFINITIONS = {
    # ========== 1. 动量类因子（23个）==========
    "momentum": [
        # 各周期收益率动量 (12个)
        ("close_ret_1d", "Ref($close, 1)/$close - 1", "1日收盘价动量"),
        ("close_ret_5d", "Ref($close, 5)/$close - 1", "5日收盘价动量"),
        ("close_ret_10d", "Ref($close, 10)/$close - 1", "10日收盘价动量"),
        ("close_ret_20d", "Ref($close, 20)/$close - 1", "20日收盘价动量"),
        ("close_ret_30d", "Ref($close, 30)/$close - 1", "30日收盘价动量"),
        ("close_ret_60d", "Ref($close, 60)/$close - 1", "60日收盘价动量"),
        ("open_ret_1d", "Ref($open, 1)/$close - 1", "1日开盘价动量"),
        ("open_ret_5d", "Ref($open, 5)/$close - 1", "5日开盘价动量"),
        ("open_ret_10d", "Ref($open, 10)/$close - 1", "10日开盘价动量"),
        ("open_ret_20d", "Ref($open, 20)/$close - 1", "20日开盘价动量"),
        ("open_ret_30d", "Ref($open, 30)/$close - 1", "30日开盘价动量"),
        ("open_ret_60d", "Ref($open, 60)/$close - 1", "60日开盘价动量"),
        # 高低价动量 (8个)
        ("high_ret_5d", "Ref($high, 5)/$close - 1", "5日最高价动量"),
        ("high_ret_10d", "Ref($high, 10)/$close - 1", "10日最高价动量"),
        ("high_ret_20d", "Ref($high, 20)/$close - 1", "20日最高价动量"),
        ("high_ret_30d", "Ref($high, 30)/$close - 1", "30日最高价动量"),
        ("low_ret_5d", "Ref($low, 5)/$close - 1", "5日最低价动量"),
        ("low_ret_10d", "Ref($low, 10)/$close - 1", "10日最低价动量"),
        ("low_ret_20d", "Ref($low, 20)/$close - 1", "20日最低价动量"),
        ("low_ret_30d", "Ref($low, 30)/$close - 1", "30日最低价动量"),
        # 累计收益率 (3个)
        ("cum_ret_5d", "$close / Ref($close, 5) - 1", "5日累计收益率"),
        ("cum_ret_10d", "$close / Ref($close, 10) - 1", "10日累计收益率"),
        ("cum_ret_20d", "$close / Ref($close, 20) - 1", "20日累计收益率"),
    ],

    # ========== 2. 波动率类因子（20个）==========
    "volatility": [
        # 价格标准差 (10个)
        ("std_5d", "Std($close, 5)/$close", "5日收盘价标准差"),
        ("std_10d", "Std($close, 10)/$close", "10日收盘价标准差"),
        ("std_20d", "Std($close, 20)/$close", "20日收盘价标准差"),
        ("std_30d", "Std($close, 30)/$close", "30日收盘价标准差"),
        ("std_60d", "Std($close, 60)/$close", "60日收盘价标准差"),
        ("retvol_5d", "Std($close / Ref($close, 1) - 1, 5)", "5日收益波动率"),
        ("retvol_10d", "Std($close / Ref($close, 1) - 1, 10)", "10日收益波动率"),
        ("retvol_20d", "Std($close / Ref($close, 1) - 1, 20)", "20日收益波动率"),
        ("retvol_30d", "Std($close / Ref($close, 1) - 1, 30)", "30日收益波动率"),
        ("retvol_60d", "Std($close / Ref($close, 1) - 1, 60)", "60日收益波动率"),
        # 价格振幅 (8个)
        ("range_daily", "($high - $low)/$close", "日内振幅"),
        ("range_avg_5d", "Mean(($high - $low)/$close, 5)", "5日平均振幅"),
        ("range_avg_10d", "Mean(($high - $low)/$close, 10)", "10日平均振幅"),
        ("range_avg_20d", "Mean(($high - $low)/$close, 20)", "20日平均振幅"),
        ("range_avg_30d", "Mean(($high - $low)/$close, 30)", "30日平均振幅"),
        ("hlratio_std_5d", "Std($high/$low, 5)", "5日高低价比波动"),
        ("hlratio_std_10d", "Std($high/$low, 10)", "10日高低价比波动"),
        ("range_std_20d", "Std(($high - $low)/$close, 20)", "20日振幅标准差"),
        # 额外的波动率指标 (2个)
        ("volatility_ratio_20d", "Std($close, 20) / Mean($close, 20)", "20日波动率比率"),
        ("atr_ratio_14d", "Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), 14) / $close", "14日ATR比率"),
    ],

    # ========== 3. 量价类因子（17个）==========
    "volprice": [
        # 成交量变化 (8个)
        ("volratio_5d", "$volume / Mean($volume, 5)", "5日成交量比率"),
        ("volratio_10d", "$volume / Mean($volume, 10)", "10日成交量比率"),
        ("volratio_20d", "$volume / Mean($volume, 20)", "20日成交量比率"),
        ("volratio_30d", "$volume / Mean($volume, 30)", "30日成交量比率"),
        ("volcv_5d", "Std($volume, 5) / Mean($volume, 5)", "5日成交量变异系数"),
        ("volcv_10d", "Std($volume, 10) / Mean($volume, 10)", "10日成交量变异系数"),
        ("volcv_20d", "Std($volume, 20) / Mean($volume, 20)", "20日成交量变异系数"),
        ("volcv_30d", "Std($volume, 30) / Mean($volume, 30)", "30日成交量变异系数"),
        # 量价相关性 (6个)
        ("pvcorr_5d", "Corr($close, $volume, 5)", "5日价量相关性"),
        ("pvcorr_10d", "Corr($close, $volume, 10)", "10日价量相关性"),
        ("pvcorr_20d", "Corr($close, $volume, 20)", "20日价量相关性"),
        ("retvolcorr_5d", "Corr($close / Ref($close, 1) - 1, $volume, 5)", "5日收益率与成交量相关性"),
        ("retvolcorr_10d", "Corr($close / Ref($close, 1) - 1, $volume, 10)", "10日收益率与成交量相关性"),
        ("retvolcorr_20d", "Corr($close / Ref($close, 1) - 1, $volume, 20)", "20日收益率与成交量相关性"),
        # 成交额因子 (3个)
        ("turnover_5d", "$close * $volume / Mean($close * $volume, 5)", "5日成交额比率"),
        ("turnover_10d", "$close * $volume / Mean($close * $volume, 10)", "10日成交额比率"),
        ("turnover_20d", "$close * $volume / Mean($close * $volume, 20)", "20日成交额比率"),
    ],

    # ========== 4. 技术指标类因子（19个）==========
    "technical": [
        # RSI指标 (3个)
        ("rsi_6", "Mean(Max($close - Ref($close, 1), 0), 6) / (Mean(Abs($close - Ref($close, 1)), 6) + 1e-12)", "6日RSI"),
        ("rsi_12", "Mean(Max($close - Ref($close, 1), 0), 12) / (Mean(Abs($close - Ref($close, 1)), 12) + 1e-12)", "12日RSI"),
        ("rsi_24", "Mean(Max($close - Ref($close, 1), 0), 24) / (Mean(Abs($close - Ref($close, 1)), 24) + 1e-12)", "24日RSI"),
        # MACD系列 (4个)
        ("ema_short_12", "EMA($close, 12) / $close - 1", "12日短期EMA"),
        ("ema_long_26", "EMA($close, 26) / $close - 1", "26日长期EMA"),
        ("macd_dif", "(EMA($close, 12) - EMA($close, 26)) / $close", "MACD DIF"),
        ("macd_dea", "EMA(EMA($close, 12) - EMA($close, 26), 9) / $close", "MACD DEA"),
        # 布林带 (4个)
        ("boll_pos_10d", "($close - Mean($close, 10)) / Std($close, 10)", "10日布林带位置"),
        ("boll_pos_20d", "($close - Mean($close, 20)) / Std($close, 20)", "20日布林带位置"),
        ("boll_width_10d", "Std($close, 10) / Mean($close, 10)", "10日布林带宽度"),
        ("boll_width_20d", "Std($close, 20) / Mean($close, 20)", "20日布林带宽度"),
        # 威廉指标 (2个)
        ("williams_6", "($close - Min($low, 6)) / (Max($high, 6) - Min($low, 6) + 1e-12)", "6日威廉指标"),
        ("williams_10", "($close - Min($low, 10)) / (Max($high, 10) - Min($low, 10) + 1e-12)", "10日威廉指标"),
        # KDJ指标 (2个)
        ("kdj_9", "($close - Min($low, 9)) / (Max($high, 9) - Min($low, 9) + 1e-12)", "9日KDJ"),
        ("kdj_14", "($close - Min($low, 14)) / (Max($high, 14) - Min($low, 14) + 1e-12)", "14日KDJ"),
        # ATR (2个)
        ("atr_14", "Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), 14) / $close", "14日ATR"),
        ("atr_20", "Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), 20) / $close", "20日ATR"),
        # CCI (2个)
        ("cci_14", "(($high + $low + $close) / 3 - Mean(($high + $low + $close) / 3, 14)) / (Std(($high + $low + $close) / 3, 14) * 0.015 + 1e-12)", "14日CCI"),
        ("cci_20", "(($high + $low + $close) / 3 - Mean(($high + $low + $close) / 3, 20)) / (Std(($high + $low + $close) / 3, 20) * 0.015 + 1e-12)", "20日CCI"),
    ],

    # ========== 5. 趋势类因子（18个）==========
    "trend": [
        # 均线交叉 (10个)
        ("ma_ratio_5_10", "Mean($close, 5) / Mean($close, 10) - 1", "5日/10日均线比率"),
        ("ma_diff_5_10", "(Mean($close, 5) - Mean($close, 10)) / $close", "5日-10日均线差"),
        ("ma_ratio_5_20", "Mean($close, 5) / Mean($close, 20) - 1", "5日/20日均线比率"),
        ("ma_diff_5_20", "(Mean($close, 5) - Mean($close, 20)) / $close", "5日-20日均线差"),
        ("ma_ratio_10_20", "Mean($close, 10) / Mean($close, 20) - 1", "10日/20日均线比率"),
        ("ma_diff_10_20", "(Mean($close, 10) - Mean($close, 20)) / $close", "10日-20日均线差"),
        ("ma_ratio_10_30", "Mean($close, 10) / Mean($close, 30) - 1", "10日/30日均线比率"),
        ("ma_diff_10_30", "(Mean($close, 10) - Mean($close, 30)) / $close", "10日-30日均线差"),
        ("ma_ratio_20_60", "Mean($close, 20) / Mean($close, 60) - 1", "20日/60日均线比率"),
        ("ma_diff_20_60", "(Mean($close, 20) - Mean($close, 60)) / $close", "20日-60日均线差"),
        # 均线斜率 (3个)
        ("ma_slope_5d", "(Mean($close, 5) - Ref(Mean($close, 5), 5)) / $close", "5日均线斜率"),
        ("ma_slope_10d", "(Mean($close, 10) - Ref(Mean($close, 10), 10)) / $close", "10日均线斜率"),
        ("ma_slope_20d", "(Mean($close, 20) - Ref(Mean($close, 20), 20)) / $close", "20日均线斜率"),
        # 价格与均线偏离 (5个)
        ("price_dev_5d", "$close / Mean($close, 5) - 1", "价格偏离5日均线"),
        ("price_dev_10d", "$close / Mean($close, 10) - 1", "价格偏离10日均线"),
        ("price_dev_20d", "$close / Mean($close, 20) - 1", "价格偏离20日均线"),
        ("price_dev_30d", "$close / Mean($close, 30) - 1", "价格偏离30日均线"),
        ("price_dev_60d", "$close / Mean($close, 60) - 1", "价格偏离60日均线"),
    ]
}


def to_class_name(category: str, suffix: str) -> str:
    """生成类名：qlib_momentum_close_ret_1d → QlibMomentumCloseRet1dFactor"""
    parts = suffix.split('_')
    capitalized = ''.join(word.capitalize() for word in parts)
    category_cap = category.capitalize()
    return f"Qlib{category_cap}{capitalized}Factor"


def to_factor_name(category: str, suffix: str) -> str:
    """生成因子名：qlib_momentum_close_ret_1d"""
    return f"qlib_{category}_{suffix}"


def generate_factor_file(category: str, factors: List[Tuple[str, str, str]], output_dir: str):
    """
    生成一个类别的因子文件

    Args:
        category: 类别名（momentum/volatility/volprice/technical/trend）
        factors: 因子定义列表 [(suffix, expression, description), ...]
        output_dir: 输出目录
    """
    filename = f"qlib_{category}_factors.py"
    filepath = os.path.join(output_dir, filename)

    # 生成文件头部
    content = f'''# -*- coding: utf-8 -*-
"""
Qlib {category.capitalize()} Factors
拆分自Alpha158的{category}类因子（共{len(factors)}个）
每个因子独立参与IC评估和权重优化
"""

from .qlib_base_factor import QlibBaseFactor


'''

    # 生成每个因子类
    class_names = []
    for suffix, expression, description in factors:
        class_name = to_class_name(category, suffix)
        factor_name = to_factor_name(category, suffix)
        class_names.append(class_name)

        content += f'''class {class_name}(QlibBaseFactor):
    """
    {description}

    Qlib表达式: {expression}
    """

    def __init__(self):
        super().__init__(
            name="{factor_name}",
            qlib_expression="{expression}",
            description="{description}"
        )


'''

    # 生成工厂函数
    content += f'''def get_{category}_factors():
    """返回所有{len(factors)}个{category}因子实例"""
    return [
'''
    for class_name in class_names:
        content += f'        {class_name}(),\n'

    content += '''    ]
'''

    # 写入文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] Generated: {filename} ({len(factors)} factors)")
    return filename, len(factors)


def main():
    """主函数：生成所有5个类别的因子文件"""
    print("=" * 60)
    print("Qlib Factor Split Code Generator")
    print("=" * 60)

    # 确定输出目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_dir = project_root / "src" / "factors"

    print(f"\nOutput Directory: {output_dir}")
    print(f"Goal: Generate 97 independent Qlib factor classes\n")

    # 生成5个类别文件
    total_factors = 0
    generated_files = []

    for category, factors in FACTOR_DEFINITIONS.items():
        filename, count = generate_factor_file(category, factors, str(output_dir))
        generated_files.append((category, filename, count))
        total_factors += count

    # 输出摘要
    print(f"\n{'='*60}")
    print("Generation Summary")
    print(f"{'='*60}")
    print(f"{'Category':<15} {'Filename':<35} {'Count':<10}")
    print("-" * 60)
    for category, filename, count in generated_files:
        print(f"{category:<15} {filename:<35} {count:<10}")
    print("-" * 60)
    print(f"{'Total':<15} {'5 files':<35} {total_factors:<10}")
    print(f"{'='*60}")

    # 验证总数
    if total_factors == 97:
        print(f"\n[SUCCESS] Generated 97 Qlib factor classes!")
    else:
        print(f"\n[WARNING] Expected 97 factors, generated {total_factors}")

    print("\nNext Steps:")
    print("1. Update src/factors/__init__.py to add registration function")
    print("2. Run tests: python test/test_qlib_split_factors.py")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
