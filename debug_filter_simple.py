#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化调试前日涨幅过滤器
找出具体错误位置
"""
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_data_provider():
    """测试数据提供者"""
    try:
        from src.data.multi_source_data_provider import MultiSourceDataProvider

        provider = MultiSourceDataProvider()

        # 测试一个具体股票
        symbol = "002759.SZ"
        print(f"测试股票: {symbol}")

        result = provider.get_stock_data(symbol)
        print(f"返回类型: {type(result)}")
        print(f"返回值: {result}")

        # 模拟过滤器中的处理
        if isinstance(result, tuple) and len(result) == 4:
            data, _, _, _ = result
            print(f"数据类型: {type(data)}")
            print(f"数据形状: {data.shape}")
            print(f"最后3行数据:")
            print(data.tail(3)[['Close']])

            # 测试日期处理
            latest_date = data.index[-1]
            print(f"最新日期: {latest_date} (类型: {type(latest_date)})")

            # 测试是否可以访问索引和列
            if hasattr(data, 'iloc'):
                latest_close = data['Close'].iloc[-1]
                print(f"最新收盘价: {latest_close}")

                # 测试iloc[-2]
                if len(data) >= 2:
                    prev_close = data['Close'].iloc[-2]
                    print(f"前日收盘价: {prev_close}")
                    print(f"涨幅计算: {(latest_close - prev_close) / prev_close * 100:.2f}%")

        return True

    except Exception as e:
        print(f"❌ 数据提供者测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_date_processing():
    """测试日期处理"""
    try:
        import pandas as pd

        # 创建测试数据
        dates = pd.date_range(start='2025-11-07', end='2025-11-10', freq='D')
        prices = [100.0, 105.0, 102.5, 103.0]  # 模拟价格变化：0% -> +5% -> -2.4% -> +0.5%

        data = pd.DataFrame({'Close': prices}, index=dates)
        print(f"测试数据:")
        print(data)

        # 测试过滤器中的日期处理逻辑
        latest_date = data.index[-1]
        print(f"\n原始最新日期: {latest_date} (类型: {type(latest_date)})")

        # 测试字符串转换
        if isinstance(latest_date, str):
            processed_date = datetime.strptime(latest_date, '%Y-%m-%d')
            print(f"字符串转换: {processed_date}")
        elif hasattr(latest_date, 'date'):
            print(f"date属性存在: {hasattr(latest_date, 'date')}")
            # 测试pandas Timestamp
            if isinstance(latest_date, type(data.index[-1])):
                processed_date = latest_date.to_pydatetime()
                print(f"Timestamp转换: {processed_date}")
            else:
                # 其他date对象
                processed_date = datetime.combine(latest_date, datetime.min.time())
                print(f"date对象组合: {processed_date}")
        else:
            # 直接处理
            print(f"直接处理: {latest_date}")
            processed_date = latest_date if isinstance(latest_date, datetime) else datetime.now()

        return True

    except Exception as e:
        print(f"❌ 日期处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行调试测试"""
    print("简化过滤器调试")
    print("测试数据提供者和日期处理")

    # 设置控制台编码
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass

    results = []

    results.append(("数据提供者", test_data_provider()))
    results.append(("日期处理", test_date_processing()))

    print(f"\n测试汇总:")
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")

    return sum(1 for _, result in results if result) == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)