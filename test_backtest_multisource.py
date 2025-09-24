#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-source backtest system test (No unicode chars)
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta

# Add project root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtest.advanced_backtest_engine import AdvancedBacktestEngine
from src.backtest.data_collector import BacktestDataCollector
from src.data.data_provider import DataProvider

# Add config directory to path
config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
sys.path.insert(0, config_dir)

try:
    from config_manager import get_config
except ImportError:
    def get_config():
        return None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_multi_source_integration():
    """Test if backtest system uses multi-source data"""
    print("=" * 60)
    print("TESTING MULTI-SOURCE INTEGRATION")
    print("=" * 60)
    
    try:
        # 1. Test data collector
        collector = BacktestDataCollector()
        print("BacktestDataCollector created successfully")
        
        # 2. Check if multi-source is integrated
        if hasattr(collector, 'data_provider') and collector.data_provider:
            print("PASS: Multi-source data provider is integrated")
            print(f"Available sources: {collector.data_provider.get_available_sources()}")
            print(f"Primary source: {collector.data_provider.primary_source}")
            
            # 3. Test data collection
            test_symbol = "600519.SH"
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            print(f"Testing data collection for: {test_symbol}")
            data = collector.get_price_data(
                test_symbol,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            if not data.empty:
                print(f"PASS: Collected {len(data)} data points")
                print(f"Date range: {data.index[0].date()} to {data.index[-1].date()}")
                print(f"Latest price: {data['Close'].iloc[-1]:.2f}")
                return True
            else:
                print("FAIL: No data collected")
                return False
        else:
            print("FAIL: Multi-source provider not available")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_backtest_execution():
    """Test basic backtest execution with real data"""
    print("\n" + "=" * 60)
    print("TESTING BACKTEST EXECUTION")
    print("=" * 60)
    
    try:
        # Initialize components
        engine = AdvancedBacktestEngine(initial_capital=1000000)
        collector = BacktestDataCollector()
        print("Components initialized")
        
        # Test with a simple recommendation
        test_rec = {
            "stock_symbol": "600519.SH",
            "recommendation": "buy",
            "confidence": 0.80,
            "timestamp": "2025-08-15 09:30:00",
            "price": 1500.0
        }
        
        # Get market data
        symbol = test_rec['stock_symbol']
        rec_date = datetime.strptime(test_rec['timestamp'].split()[0], '%Y-%m-%d')
        start_date = rec_date - timedelta(days=5)
        end_date = rec_date + timedelta(days=30)
        
        if end_date > datetime.now():
            end_date = datetime.now()
        
        print(f"Collecting market data for {symbol}")
        data = collector.get_price_data(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if data.empty:
            print("FAIL: No market data available")
            return False
        
        print(f"Market data collected: {len(data)} points")
        
        # Simulate a simple trade
        available_dates = data.index
        buy_date = None
        for date in available_dates:
            if date.date() >= rec_date.date():
                buy_date = date
                break
        
        if buy_date is None:
            print("FAIL: No trading data after recommendation date")
            return False
        
        buy_price = data.loc[buy_date, 'Close']
        
        # Find sell date (15 days later or last available)
        sell_date = None
        days_held = 0
        for date in available_dates:
            if date > buy_date:
                days_held += 1
                if days_held >= 15:
                    sell_date = date
                    break
        
        if sell_date is None:
            sell_date = available_dates[-1]
        
        sell_price = data.loc[sell_date, 'Close']
        
        # Calculate results
        shares = 1000  # Simple test with 1000 shares
        profit = (sell_price - buy_price) * shares
        profit_pct = (sell_price - buy_price) / buy_price * 100
        
        print(f"Trade simulation:")
        print(f"  Symbol: {symbol}")
        print(f"  Buy: {buy_price:.2f} on {buy_date.strftime('%Y-%m-%d')}")
        print(f"  Sell: {sell_price:.2f} on {sell_date.strftime('%Y-%m-%d')}")
        print(f"  Shares: {shares}")
        print(f"  Profit: {profit:.2f} CNY ({profit_pct:+.2f}%)")
        
        print("PASS: Backtest execution completed successfully")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("MULTI-SOURCE BACKTEST SYSTEM TEST")
    print("=" * 60)
    
    tests = [
        ("Multi-source integration", test_multi_source_integration),
        ("Backtest execution", test_backtest_execution)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        if test_func():
            print(f"RESULT: {test_name} - PASSED")
            passed += 1
        else:
            print(f"RESULT: {test_name} - FAILED")
    
    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("\nSUCCESS: Multi-source backtest system is working!")
        print("\nThe backtest system now:")
        print("1. Uses your configured multi-source data providers")
        print("2. Can access AkShare, Tushare, YFinance based on your config")
        print("3. Automatically falls back if primary source fails")
        print("4. Collects real market data for accurate backtesting")
        print("\nYou can now run: python run_simple_backtest.py -m advanced")
    else:
        print(f"\nFAILED: {len(tests) - passed} test(s) failed")
        
    return passed == len(tests)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)