# -*- coding: utf-8 -*-
"""
技术面AI因子
包含形态识别、量价关系等AI增强的技术分析因子
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
from scipy import stats
from scipy.signal import find_peaks
import warnings
warnings.filterwarnings('ignore')

# 可选依赖的导入和容错处理
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    print("警告: TA-Lib库未安装，将使用替代实现。建议运行: pip install TA-Lib")
    TALIB_AVAILABLE = False

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    print("警告: scikit-learn库未安装，部分AI功能将被禁用。建议运行: pip install scikit-learn")
    SKLEARN_AVAILABLE = False

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)

class PatternRecognitionFactor(BaseFactor):
    """技术形态识别因子"""
    
    def __init__(self):
        super().__init__(
            name="pattern_recognition", 
            category="technical",
            description="AI识别技术分析中的经典形态模式"
        )
        self.dependencies = ["price", "volume"]
        self.lookback_days = 30
    
    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算形态识别因子"""
        # 获取价格和成交量数据，避免concat操作
        price_df = data["price"].tail(self.lookback_days).copy()
        volume_df = data["volume"].tail(self.lookback_days).copy()
        
        # 确保数据长度一致
        min_len = min(len(price_df), len(volume_df))
        if min_len < 20:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)
            
        # 只保留相同长度的数据
        price_df = price_df.tail(min_len).reset_index(drop=True)
        volume_df = volume_df.tail(min_len).reset_index(drop=True)
        
        # 为计算方法创建完整的DataFrame（手动添加Volume列）
        price_data = price_df.copy()
        price_data['Volume'] = volume_df['Volume'].values
        
        # 计算各种形态分数
        pattern_scores = {
            'trend_strength': self._calculate_trend_strength(price_data),
            'support_resistance': self._identify_support_resistance(price_data),
            'reversal_patterns': self._detect_reversal_patterns(price_data),
            'continuation_patterns': self._detect_continuation_patterns(price_data),
            'breakout_strength': self._calculate_breakout_strength(price_data)
        }
        
        # AI增强：使用加权方式综合各种形态分数
        weights = {
            'trend_strength': 0.25,
            'support_resistance': 0.20,
            'reversal_patterns': 0.25,
            'continuation_patterns': 0.15,
            'breakout_strength': 0.15
        }
        
        final_score = sum(pattern_scores[key] * weights[key] for key in pattern_scores)
        
        # 标准化到[-1, 1]区间
        final_score = np.tanh(final_score)
        
        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=final_score,
            timestamp=datetime.now(),
            confidence=0.8,
            raw_data=pattern_scores
        )
    
    def _calculate_trend_strength(self, data: pd.DataFrame) -> float:
        """计算趋势强度"""
        closes = data['Close'].values
        
        # 线性回归趋势
        x = np.arange(len(closes))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, closes)
        
        # 趋势一致性（价格相对于趋势线的偏差）
        trend_line = slope * x + intercept
        deviations = np.abs(closes - trend_line)
        trend_consistency = 1.0 - (np.mean(deviations) / np.mean(closes))
        
        # 趋势强度 = 斜率标准化 * R平方 * 一致性
        slope_normalized = np.tanh(slope / np.std(closes) * len(closes))
        trend_strength = slope_normalized * (r_value ** 2) * trend_consistency
        
        return trend_strength
    
    def _identify_support_resistance(self, data: pd.DataFrame) -> float:
        """识别支撑阻力位强度"""
        highs = data['High'].values
        lows = data['Low'].values
        closes = data['Close'].values
        
        # 寻找局部极值点
        high_peaks, _ = find_peaks(highs, distance=3)
        low_peaks, _ = find_peaks(-lows, distance=3)
        
        # 计算支撑阻力位的聚集度
        current_price = closes[-1]
        
        # 阻力位分析
        resistance_levels = highs[high_peaks]
        resistance_strength = 0.0
        if len(resistance_levels) > 0:
            # 找到最接近当前价格的阻力位
            nearest_resistance = resistance_levels[np.argmin(np.abs(resistance_levels - current_price))]
            if nearest_resistance > current_price:
                # 距离阻力位越近，阻力强度越高（负值）
                resistance_strength = -(1.0 - (nearest_resistance - current_price) / current_price)
        
        # 支撑位分析
        support_levels = lows[low_peaks]
        support_strength = 0.0
        if len(support_levels) > 0:
            nearest_support = support_levels[np.argmin(np.abs(support_levels - current_price))]
            if nearest_support < current_price:
                # 距离支撑位越近，支撑强度越高（正值）
                support_strength = 1.0 - (current_price - nearest_support) / current_price
        
        return support_strength + resistance_strength
    
    def _detect_reversal_patterns(self, data: pd.DataFrame) -> float:
        """检测反转形态"""
        closes = data['Close'].values
        highs = data['High'].values
        lows = data['Low'].values
        
        if len(closes) < 10:
            return 0.0
        
        reversal_score = 0.0
        
        # 双顶/双底检测
        peaks, _ = find_peaks(highs, distance=5)
        troughs, _ = find_peaks(-lows, distance=5)
        
        # 双顶检测
        if len(peaks) >= 2:
            last_peaks = highs[peaks[-2:]]
            if abs(last_peaks[0] - last_peaks[1]) / last_peaks[0] < 0.03:  # 价格相近
                # 检查中间是否有明显回调
                middle_low = np.min(lows[peaks[-2]:peaks[-1]])
                if (last_peaks[0] - middle_low) / last_peaks[0] > 0.05:  # 回调幅度>5%
                    reversal_score -= 0.5  # 看跌信号
        
        # 双底检测
        if len(troughs) >= 2:
            last_troughs = lows[troughs[-2:]]
            if abs(last_troughs[0] - last_troughs[1]) / last_troughs[0] < 0.03:
                middle_high = np.max(highs[troughs[-2]:troughs[-1]])
                if (middle_high - last_troughs[0]) / last_troughs[0] > 0.05:
                    reversal_score += 0.5  # 看涨信号
        
        # 头肩顶/头肩底的简化检测
        if len(peaks) >= 3:
            last_three_peaks = highs[peaks[-3:]]
            # 头肩顶：中间高，两边相对低且相近
            if (last_three_peaks[1] > last_three_peaks[0] and 
                last_three_peaks[1] > last_three_peaks[2] and
                abs(last_three_peaks[0] - last_three_peaks[2]) / last_three_peaks[0] < 0.05):
                reversal_score -= 0.3
        
        return reversal_score
    
    def _detect_continuation_patterns(self, data: pd.DataFrame) -> float:
        """检测持续形态"""
        closes = data['Close'].values
        highs = data['High'].values
        lows = data['Low'].values
        
        if len(closes) < 15:
            return 0.0
        
        continuation_score = 0.0
        
        # 三角形整理检测
        recent_highs = highs[-15:]
        recent_lows = lows[-15:]
        
        # 上升三角形：高点相近，低点上移
        high_peaks, _ = find_peaks(recent_highs, distance=3)
        low_peaks, _ = find_peaks(-recent_lows, distance=3)
        
        if len(high_peaks) >= 2 and len(low_peaks) >= 2:
            # 检查高点是否水平
            high_slope = np.polyfit(high_peaks, recent_highs[high_peaks], 1)[0]
            # 检查低点是否上升
            low_slope = np.polyfit(low_peaks, recent_lows[low_peaks], 1)[0]
            
            if abs(high_slope) < 0.01 and low_slope > 0:  # 上升三角形
                continuation_score += 0.3
            elif abs(low_slope) < 0.01 and high_slope < 0:  # 下降三角形
                continuation_score -= 0.3
        
        # 旗形整理检测（简化版）
        # 通过价格波动率的变化来识别
        volatility_early = np.std(closes[-20:-10])
        volatility_recent = np.std(closes[-10:])
        
        if volatility_recent < volatility_early * 0.7:  # 波动率显著下降
            # 检查整理前的趋势方向
            trend_slope = np.polyfit(range(10), closes[-20:-10], 1)[0]
            if trend_slope > 0:
                continuation_score += 0.2  # 看涨旗形
            else:
                continuation_score -= 0.2  # 看跌旗形
        
        return continuation_score
    
    def _calculate_breakout_strength(self, data: pd.DataFrame) -> float:
        """计算突破强度"""
        closes = data['Close'].values
        volumes = data['Volume'].values
        highs = data['High'].values
        lows = data['Low'].values
        
        if len(closes) < 10:
            return 0.0
        
        # 计算移动平均作为参考线
        ma20 = pd.Series(closes).rolling(window=min(20, len(closes))).mean().values
        ma5 = pd.Series(closes).rolling(window=min(5, len(closes))).mean().values
        
        current_price = closes[-1]
        breakout_score = 0.0
        
        # 价格突破移动平均线
        if len(ma20) > 0 and not np.isnan(ma20[-1]):
            ma_breakout = (current_price - ma20[-1]) / ma20[-1]
            breakout_score += np.tanh(ma_breakout * 10)  # 标准化
        
        # 成交量确认
        if len(volumes) >= 5:
            recent_vol = np.mean(volumes[-3:])
            avg_vol = np.mean(volumes[-20:-3]) if len(volumes) >= 20 else np.mean(volumes[:-3])
            
            if avg_vol > 0:
                vol_ratio = recent_vol / avg_vol
                if vol_ratio > 1.5:  # 成交量放大
                    breakout_score *= 1.2  # 增强突破信号
                elif vol_ratio < 0.5:  # 成交量萎缩
                    breakout_score *= 0.8  # 弱化突破信号
        
        return breakout_score


class VolumePatternFactor(BaseFactor):
    """量价关系AI因子"""
    
    def __init__(self):
        super().__init__(
            name="volume_pattern",
            category="technical",
            description="AI分析量价关系模式，识别资金流向"
        )
        self.dependencies = ["price", "volume"]
        self.lookback_days = 20
    
    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算量价关系因子"""
        # 获取价格和成交量数据，避免concat操作
        price_df = data["price"].tail(self.lookback_days).copy()
        volume_df = data["volume"].tail(self.lookback_days).copy()
        
        # 确保数据长度一致
        min_len = min(len(price_df), len(volume_df))
        if min_len < 10:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)
            
        # 只保留相同长度的数据
        price_df = price_df.tail(min_len).reset_index(drop=True)
        volume_df = volume_df.tail(min_len).reset_index(drop=True)
        
        # 为计算方法创建完整的DataFrame（手动添加Volume列）
        df = price_df.copy()
        df['Volume'] = volume_df['Volume'].values
        
        # 计算各种量价关系指标
        vp_scores = {
            'price_volume_correlation': self._calculate_pv_correlation(df),
            'volume_trend_consistency': self._analyze_volume_trend(df),
            'buying_selling_pressure': self._calculate_pressure_index(df),
            'volume_profile_analysis': self._analyze_volume_profile(df),
            'abnormal_volume_impact': self._detect_abnormal_volume(df)
        }
        
        # AI整合：动态权重分配
        weights = self._calculate_dynamic_weights(df, vp_scores)
        
        final_score = sum(vp_scores[key] * weights[key] for key in vp_scores)
        
        # 应用非线性变换增强信号
        final_score = self._enhance_signal(final_score, df)
        
        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=final_score,
            timestamp=datetime.now(),
            confidence=0.85,
            raw_data=vp_scores,
            metadata={'weights': weights}
        )
    
    def _calculate_pv_correlation(self, df: pd.DataFrame) -> float:
        """计算价格与成交量的相关性"""
        price_changes = df['Close'].pct_change().dropna()
        volume_changes = df['Volume'].pct_change().dropna()
        
        if len(price_changes) < 5 or len(volume_changes) < 5:
            return 0.0
        
        # 对齐数据长度
        min_len = min(len(price_changes), len(volume_changes))
        price_changes = price_changes[-min_len:]
        volume_changes = volume_changes[-min_len:]
        
        # 计算相关系数
        correlation = np.corrcoef(price_changes, volume_changes)[0, 1]
        
        if np.isnan(correlation):
            return 0.0
        
        # 正相关表示健康的量价配合
        return correlation
    
    def _analyze_volume_trend(self, df: pd.DataFrame) -> float:
        """分析成交量趋势一致性"""
        closes = df['Close'].values
        volumes = df['Volume'].values
        
        # 计算价格趋势
        price_trend = np.polyfit(range(len(closes)), closes, 1)[0]
        
        # 计算成交量趋势
        volume_trend = np.polyfit(range(len(volumes)), volumes, 1)[0]
        
        # 标准化趋势
        price_trend_norm = price_trend / np.mean(closes)
        volume_trend_norm = volume_trend / np.mean(volumes)
        
        # 量价趋势一致性评分
        if price_trend_norm > 0 and volume_trend_norm > 0:
            # 价格上涨 + 成交量放大 = 积极信号
            return min(1.0, abs(price_trend_norm) * abs(volume_trend_norm) * 100)
        elif price_trend_norm < 0 and volume_trend_norm > 0:
            # 价格下跌 + 成交量放大 = 消极信号
            return max(-1.0, -abs(price_trend_norm) * abs(volume_trend_norm) * 100)
        else:
            # 其他情况权重较低
            return price_trend_norm * volume_trend_norm * 50
    
    def _calculate_pressure_index(self, df: pd.DataFrame) -> float:
        """计算买卖压力指数"""
        # 使用收盘价相对于最高最低价的位置判断买卖压力
        high_low_range = df['High'] - df['Low']
        close_position = (df['Close'] - df['Low']) / high_low_range
        
        # 避免除零
        close_position = close_position.fillna(0.5)
        
        # 结合成交量加权
        volume_weights = df['Volume'] / df['Volume'].sum()
        pressure_index = (close_position * volume_weights).sum()
        
        # 标准化到[-1, 1]
        pressure_score = (pressure_index - 0.5) * 2
        
        return pressure_score
    
    def _analyze_volume_profile(self, df: pd.DataFrame) -> float:
        """分析成交量分布模式"""
        volumes = df['Volume'].values
        prices = df['Close'].values
        
        if len(volumes) < 5:
            return 0.0
        
        # 将价格分段，分析各段的成交量分布
        try:
            # 使用KMeans将价格分为3个区间
            price_reshape = prices.reshape(-1, 1)
            scaler = StandardScaler()
            price_scaled = scaler.fit_transform(price_reshape)
            
            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            price_clusters = kmeans.fit_predict(price_scaled)
            
            # 计算每个价格区间的平均成交量
            cluster_volumes = []
            for i in range(3):
                cluster_mask = (price_clusters == i)
                if np.any(cluster_mask):
                    cluster_volumes.append(np.mean(volumes[cluster_mask]))
                else:
                    cluster_volumes.append(0)
            
            # 分析成交量分布特征
            volume_concentration = np.std(cluster_volumes) / (np.mean(cluster_volumes) + 1e-8)
            
            # 当前价格所在区间的成交量相对强度
            current_cluster = price_clusters[-1]
            current_cluster_volume = cluster_volumes[current_cluster]
            avg_volume = np.mean(cluster_volumes)
            
            relative_strength = (current_cluster_volume - avg_volume) / (avg_volume + 1e-8)
            
            return np.tanh(relative_strength + volume_concentration)
            
        except Exception as e:
            logger.debug(f"成交量分布分析失败: {e}")
            return 0.0
    
    def _detect_abnormal_volume(self, df: pd.DataFrame) -> float:
        """检测异常成交量的影响"""
        volumes = df['Volume'].values
        price_changes = df['Close'].pct_change().abs().values
        
        # 计算成交量的统计特征
        volume_mean = np.mean(volumes)
        volume_std = np.std(volumes)
        
        # 识别异常成交量（超过2个标准差）
        abnormal_threshold = volume_mean + 2 * volume_std
        abnormal_mask = volumes > abnormal_threshold
        
        if not np.any(abnormal_mask):
            return 0.0
        
        # 计算异常成交量期间的价格影响
        abnormal_price_impact = np.mean(price_changes[abnormal_mask])
        normal_price_impact = np.mean(price_changes[~abnormal_mask])
        
        # 异常成交量的相对影响
        if normal_price_impact > 0:
            impact_ratio = abnormal_price_impact / normal_price_impact
        else:
            impact_ratio = 1.0
        
        # 最近是否出现异常成交量
        recent_abnormal = np.any(abnormal_mask[-3:])  # 最近3天
        
        base_score = np.tanh(impact_ratio - 1)  # 标准化
        
        if recent_abnormal:
            base_score *= 1.5  # 放大最近异常成交量的影响
        
        return base_score
    
    def _calculate_dynamic_weights(self, df: pd.DataFrame, scores: Dict[str, float]) -> Dict[str, float]:
        """根据市场状态动态计算权重"""
        # 基础权重
        base_weights = {
            'price_volume_correlation': 0.25,
            'volume_trend_consistency': 0.25,
            'buying_selling_pressure': 0.20,
            'volume_profile_analysis': 0.15,
            'abnormal_volume_impact': 0.15
        }
        
        # 根据波动率调整权重
        volatility = df['Close'].pct_change().std()
        
        if volatility > 0.05:  # 高波动环境
            # 在高波动环境下，更重视异常成交量和买卖压力
            base_weights['abnormal_volume_impact'] *= 1.3
            base_weights['buying_selling_pressure'] *= 1.2
            base_weights['price_volume_correlation'] *= 0.8
        else:  # 低波动环境
            # 在低波动环境下，更重视趋势一致性
            base_weights['volume_trend_consistency'] *= 1.3
            base_weights['price_volume_correlation'] *= 1.2
            base_weights['abnormal_volume_impact'] *= 0.7
        
        # 归一化权重
        total_weight = sum(base_weights.values())
        normalized_weights = {k: v / total_weight for k, v in base_weights.items()}
        
        return normalized_weights
    
    def _enhance_signal(self, raw_score: float, df: pd.DataFrame) -> float:
        """使用AI技术增强信号"""
        # 应用非线性变换
        enhanced_score = np.tanh(raw_score * 2)  # 增强信号强度
        
        # 根据最近趋势调整
        recent_trend = df['Close'].iloc[-5:].pct_change().mean()
        if abs(recent_trend) > 0.02:  # 明显趋势
            enhanced_score *= (1 + abs(recent_trend) * 10)  # 放大趋势环境下的信号
        
        # 限制在[-1, 1]区间
        return np.clip(enhanced_score, -1.0, 1.0)


class OBVFactor(BaseFactor):
    """OBV能量潮因子"""

    def __init__(self):
        super().__init__(
            name="obv",
            category="technical",
            description="OBV(On-Balance Volume)能量潮指标，衡量累积买卖压力"
        )
        self.dependencies = ["price", "volume"]
        self.lookback_days = 30

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算OBV因子"""
        price_df = data["price"].tail(self.lookback_days).copy()
        volume_df = data["volume"].tail(self.lookback_days).copy()

        min_len = min(len(price_df), len(volume_df))
        if min_len < 10:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        price_df = price_df.tail(min_len).reset_index(drop=True)
        volume_df = volume_df.tail(min_len).reset_index(drop=True)

        closes = price_df['Close'].values
        volumes = volume_df['Volume'].values

        obv = self._calculate_obv(closes, volumes)

        obv_scores = {
            'obv_trend': self._calculate_obv_trend(obv),
            'obv_divergence': self._detect_obv_divergence(closes, obv),
            'obv_momentum': self._calculate_obv_momentum(obv),
            'obv_vs_ma': self._calculate_obv_vs_ma(obv)
        }

        weights = {
            'obv_trend': 0.35,
            'obv_divergence': 0.30,
            'obv_momentum': 0.20,
            'obv_vs_ma': 0.15
        }

        final_score = sum(obv_scores[key] * weights[key] for key in obv_scores)
        final_score = np.tanh(final_score)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=final_score,
            timestamp=datetime.now(),
            confidence=0.80,
            raw_data=obv_scores
        )

    def _calculate_obv(self, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        """计算OBV值，优先使用TA-Lib"""
        if TALIB_AVAILABLE:
            return talib.OBV(closes, volumes.astype(float))
        else:
            obv = np.zeros(len(closes))
            obv[0] = volumes[0]
            for i in range(1, len(closes)):
                if closes[i] > closes[i - 1]:
                    obv[i] = obv[i - 1] + volumes[i]
                elif closes[i] < closes[i - 1]:
                    obv[i] = obv[i - 1] - volumes[i]
                else:
                    obv[i] = obv[i - 1]
            return obv

    def _calculate_obv_trend(self, obv: np.ndarray) -> float:
        """计算OBV趋势强度"""
        x = np.arange(len(obv))
        slope, _, r_value, _, _ = stats.linregress(x, obv)
        slope_norm = np.tanh(slope / (np.std(obv) + 1e-8) * len(obv) * 0.1)
        return slope_norm * (r_value ** 2)

    def _detect_obv_divergence(self, closes: np.ndarray, obv: np.ndarray) -> float:
        """检测价格与OBV的背离"""
        half = len(closes) // 2
        price_first = closes[:half]
        price_second = closes[half:]
        obv_first = obv[:half]
        obv_second = obv[half:]

        price_change = np.mean(price_second) - np.mean(price_first)
        obv_change = np.mean(obv_second) - np.mean(obv_first)

        # 顶背离：价格涨但OBV不跟 → 看跌
        if price_change > 0 and obv_change <= 0:
            return -0.5 - min(abs(price_change / (np.mean(closes) + 1e-8)), 0.5)
        # 底背离：价格跌但OBV不跟 → 看涨
        elif price_change < 0 and obv_change >= 0:
            return 0.5 + min(abs(price_change / (np.mean(closes) + 1e-8)), 0.5)
        # 同向确认
        elif price_change > 0 and obv_change > 0:
            return 0.3
        elif price_change < 0 and obv_change < 0:
            return -0.3
        return 0.0

    def _calculate_obv_momentum(self, obv: np.ndarray) -> float:
        """计算OBV动量（5日变化率）"""
        if len(obv) < 6:
            return 0.0
        roc = (obv[-1] - obv[-6]) / (abs(obv[-6]) + 1e-8)
        return np.tanh(roc * 5)

    def _calculate_obv_vs_ma(self, obv: np.ndarray) -> float:
        """计算OBV相对其均线的位置"""
        if len(obv) < 10:
            return 0.0
        ma = np.mean(obv[-10:])
        if ma == 0:
            return 0.0
        ratio = (obv[-1] - ma) / (abs(ma) + 1e-8)
        return np.tanh(ratio * 5)


# 注册因子的函数
def register_technical_ai_factors():
    """注册所有技术面AI因子"""
    from .factor_manager import get_factor_manager
    
    factor_manager = get_factor_manager()
    
    # 注册形态识别因子
    factor_manager.register_factor(PatternRecognitionFactor())
    
    # 注册量价关系因子
    factor_manager.register_factor(VolumePatternFactor())

    # 注册OBV能量潮因子
    factor_manager.register_factor(OBVFactor())

    logger.info("技术面AI因子注册完成")