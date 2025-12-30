# -*- coding: utf-8 -*-
"""
改进选股稳定性的建议方案
"""

# ============================================================
# 方案A1：固定核心股票池 + 动态补充
# ============================================================

def improved_select_stocks_with_core_pool(self):
    """
    改进版选股逻辑：固定核心池 + 动态补充

    核心思想：
    - 70%股票来自固定核心池（每天相同）
    - 30%股票动态选择（捕捉机会）
    """

    # 1. 核心股票池（固定）- 例如从配置中选择前30只
    core_pool = self._get_fixed_core_pool(size=30)  # 每天相同

    # 2. 动态补充池 - 龙虎榜、社交媒体等
    dynamic_pool = self._get_dynamic_supplements(size=15)  # 每天变化

    # 3. 合并（去重）
    final_stocks = self._merge_pools(core_pool, dynamic_pool, max_size=40)

    return final_stocks

# ============================================================
# 方案A2：分层IC评估
# ============================================================

def stratified_ic_evaluation(self):
    """
    分层IC评估：按股票特征分组

    好处：
    - 控制股票池变化的影响
    - 更准确的因子评估
    """

    # 按市值分层
    large_cap_stocks = [s for s in stocks if s.market_cap > 500]  # >500亿
    mid_cap_stocks = [s for s in stocks if 100 < s.market_cap <= 500]
    small_cap_stocks = [s for s in stocks if s.market_cap <= 100]

    # 分别计算IC
    ic_large = calculate_ic(large_cap_stocks, factors, returns)
    ic_mid = calculate_ic(mid_cap_stocks, factors, returns)
    ic_small = calculate_ic(small_cap_stocks, factors, returns)

    # 加权平均（按样本数）
    weighted_ic = (
        ic_large * len(large_cap_stocks) +
        ic_mid * len(mid_cap_stocks) +
        ic_small * len(small_cap_stocks)
    ) / len(stocks)

    return weighted_ic

# ============================================================
# 方案A3：记录股票池信息
# ============================================================

def record_stock_pool_metadata(self, date, stocks):
    """
    记录每天股票池的元数据

    用于：
    - 后续分析股票池变化
    - IC评估时考虑股票池相似度
    """

    metadata = {
        'date': date,
        'stock_count': len(stocks),
        'avg_market_cap': np.mean([s.market_cap for s in stocks]),
        'sector_distribution': self._count_sectors(stocks),
        'source_distribution': self._count_sources(stocks),
        'stock_symbols': [s.symbol for s in stocks]  # 用于计算重叠度
    }

    # 保存到数据库或文件
    self.stock_pool_history.append(metadata)

    return metadata

# ============================================================
# 方案A4：计算股票池重叠度
# ============================================================

def calculate_pool_overlap(pool1, pool2):
    """
    计算两天股票池的重叠度

    Returns:
        overlap_ratio: 0.0-1.0，重叠比例
    """
    symbols1 = set(pool1)
    symbols2 = set(pool2)

    intersection = symbols1 & symbols2
    union = symbols1 | symbols2

    overlap_ratio = len(intersection) / len(union) if union else 0.0

    return overlap_ratio

# ============================================================
# 方案A5：只在高重叠度时计算IC
# ============================================================

def conditional_ic_calculation(self):
    """
    只在股票池重叠度较高时才计算IC

    避免：
    - 不可比股票池导致IC失真
    """

    min_overlap_threshold = 0.4  # 至少40%重叠

    for i in range(1, len(trading_dates)):
        today = trading_dates[i]
        yesterday = trading_dates[i-1]

        # 计算重叠度
        overlap = self.calculate_pool_overlap(
            stock_pool_history[yesterday],
            stock_pool_history[today]
        )

        if overlap >= min_overlap_threshold:
            # 重叠度足够，计算IC
            ic = self.calculate_ic(today)
            ic_history.append(ic)
        else:
            # 重叠度不足，跳过
            logger.info(f"{today}: 股票池重叠度仅{overlap:.1%}，跳过IC计算")

    return ic_history
