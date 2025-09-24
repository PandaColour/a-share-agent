# -*- coding: utf-8 -*-
"""
价格预测因子
包含14天高点预测、收益率预测等基于AI和统计方法的预测因子
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
from scipy import stats
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')

# 可选依赖的导入和容错处理
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error
    SKLEARN_AVAILABLE = True
except ImportError:
    print("警告: scikit-learn库未安装，将使用基础统计方法。建议运行: pip install scikit-learn")
    SKLEARN_AVAILABLE = False

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)

class PricePredictionFactor(BaseFactor):
    """14天价格高点预测因子"""
    
    def __init__(self):
        super().__init__(
            name="price_prediction_14d", 
            category="prediction",
            description="预测未来14天内可能的价格高点和收益率"
        )
        self.dependencies = ["price", "volume"]
        self.lookback_days = 60  # 使用更长的历史数据进行预测
        self.prediction_days = 14
    
    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算14天价格预测因子"""
        # 获取价格和成交量数据
        price_df = data["price"].tail(self.lookback_days).copy()
        volume_df = data["volume"].tail(self.lookback_days).copy()
        
        # 确保数据长度一致
        min_len = min(len(price_df), len(volume_df))
        if min_len < 30:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)
            
        # 创建完整的数据集
        df = price_df.tail(min_len).copy()
        df['Volume'] = volume_df.tail(min_len)['Volume'].values
        
        # 计算预测结果
        prediction_results = self._calculate_price_predictions(df, symbol)
        
        # 综合评分：基于预测的期望收益和置信度
        expected_return = prediction_results['expected_14d_return']
        prediction_confidence = prediction_results['prediction_confidence']
        
        # 综合因子值：期望收益 * 置信度
        factor_value = expected_return * prediction_confidence
        
        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=factor_value,
            timestamp=datetime.now(),
            confidence=prediction_confidence,
            raw_data=prediction_results
        )
    
    def _calculate_price_predictions(self, df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """计算价格预测"""
        current_price = df['Close'].iloc[-1]
        
        # 方法1: 技术分析预测
        technical_prediction = self._technical_analysis_prediction(df)
        
        # 方法2: 统计模型预测
        statistical_prediction = self._statistical_model_prediction(df)
        
        # 方法3: 机器学习预测（如果可用）
        ml_prediction = self._machine_learning_prediction(df) if SKLEARN_AVAILABLE else None
        
        # 方法4: 蒙特卡洛模拟
        monte_carlo_prediction = self._monte_carlo_simulation(df)
        
        # 综合所有预测方法
        predictions = [technical_prediction, statistical_prediction, monte_carlo_prediction]
        if ml_prediction:
            predictions.append(ml_prediction)
        
        # 加权平均预测结果
        weights = self._calculate_prediction_weights(df, predictions)
        
        # 计算综合预测
        weighted_high_price = sum(pred['predicted_high'] * weights[i] for i, pred in enumerate(predictions))
        weighted_return = sum(pred['expected_return'] * weights[i] for i, pred in enumerate(predictions))
        avg_confidence = sum(pred['confidence'] * weights[i] for i, pred in enumerate(predictions))
        
        # 计算预测区间
        prediction_std = np.std([pred['expected_return'] for pred in predictions])
        lower_bound = weighted_return - 1.96 * prediction_std
        upper_bound = weighted_return + 1.96 * prediction_std
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'predicted_14d_high': weighted_high_price,
            'expected_14d_return': weighted_return,
            'prediction_confidence': avg_confidence,
            'prediction_interval': (lower_bound, upper_bound),
            'prediction_std': prediction_std,
            'individual_predictions': predictions,
            'prediction_weights': weights,
            'prediction_date': datetime.now(),
            'target_date': datetime.now() + timedelta(days=self.prediction_days)
        }
    
    def _technical_analysis_prediction(self, df: pd.DataFrame) -> Dict[str, float]:
        """基于技术分析的预测"""
        closes = df['Close'].values
        highs = df['High'].values
        lows = df['Low'].values
        volumes = df['Volume'].values
        current_price = closes[-1]
        
        # 计算技术指标
        # 移动平均
        ma5 = np.mean(closes[-5:])
        ma20 = np.mean(closes[-20:])
        ma_trend = (ma5 - ma20) / ma20
        
        # ATR (平均真实波幅)
        tr = np.maximum(highs[1:] - lows[1:], 
                       np.maximum(np.abs(highs[1:] - closes[:-1]), 
                                 np.abs(lows[1:] - closes[:-1])))
        atr = np.mean(tr[-14:])  # 14日ATR
        
        # 布林带
        ma_bb = np.mean(closes[-20:])
        std_bb = np.std(closes[-20:])
        upper_band = ma_bb + 2 * std_bb
        lower_band = ma_bb - 2 * std_bb
        bb_position = (current_price - lower_band) / (upper_band - lower_band)
        
        # RSI
        price_changes = np.diff(closes)
        gains = np.where(price_changes > 0, price_changes, 0)
        losses = np.where(price_changes < 0, -price_changes, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        rsi = 100 - (100 / (1 + avg_gain / (avg_loss + 1e-8)))
        
        # 支撑阻力位
        support_resistance = self._calculate_support_resistance(df)
        
        # 基于技术指标预测价格目标
        # 趋势预测
        trend_target = current_price * (1 + ma_trend * 0.5)  # 基于均线趋势
        
        # 波动率预测
        volatility_target = current_price + atr * 2  # 基于ATR的目标价
        
        # 布林带预测
        if bb_position < 0.2:  # 接近下轨，预期反弹
            bb_target = upper_band
        elif bb_position > 0.8:  # 接近上轨，预期回调
            bb_target = ma_bb
        else:
            bb_target = current_price * 1.02  # 中性预期
        
        # RSI预测
        if rsi < 30:  # 超卖，预期反弹
            rsi_multiplier = 1.05
        elif rsi > 70:  # 超买，预期回调
            rsi_multiplier = 0.98
        else:
            rsi_multiplier = 1.01
        
        rsi_target = current_price * rsi_multiplier
        
        # 支撑阻力位预测
        resistance_target = support_resistance.get('nearest_resistance', current_price * 1.03)
        
        # 综合预测目标（取加权平均）
        targets = [trend_target, volatility_target, bb_target, rsi_target, resistance_target]
        weights = [0.25, 0.20, 0.20, 0.15, 0.20]
        predicted_high = sum(target * weight for target, weight in zip(targets, weights))
        
        # 计算预期收益率
        expected_return = (predicted_high - current_price) / current_price
        
        # 计算置信度（基于技术指标的一致性）
        signal_strength = abs(ma_trend) + (1 - abs(bb_position - 0.5) * 2) + abs(rsi - 50) / 50
        confidence = min(0.9, signal_strength / 3)
        
        return {
            'predicted_high': predicted_high,
            'expected_return': expected_return,
            'confidence': confidence,
            'method': 'technical_analysis',
            'details': {
                'ma_trend': ma_trend,
                'atr': atr,
                'bb_position': bb_position,
                'rsi': rsi,
                'targets': dict(zip(['trend', 'volatility', 'bollinger', 'rsi', 'resistance'], targets))
            }
        }
    
    def _statistical_model_prediction(self, df: pd.DataFrame) -> Dict[str, float]:
        """基于统计模型的预测"""
        closes = df['Close'].values
        current_price = closes[-1]
        
        # ARIMA简化版：自回归模型
        returns = np.diff(np.log(closes))
        
        if len(returns) < 20:
            return {
                'predicted_high': current_price * 1.02,
                'expected_return': 0.02,
                'confidence': 0.3,
                'method': 'statistical_fallback'
            }
        
        # 估计收益率的统计特征
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # 考虑自相关性
        lag1_corr = np.corrcoef(returns[1:], returns[:-1])[0, 1] if len(returns) > 1 else 0
        
        # 预测未来14天的累积收益
        # 考虑均值回归和自相关
        predicted_returns = []
        last_return = returns[-1]
        
        for day in range(self.prediction_days):
            # 简单AR(1)模型
            next_return = mean_return + lag1_corr * (last_return - mean_return)
            predicted_returns.append(next_return)
            last_return = next_return
        
        # 计算累积收益和最大值
        cumulative_returns = np.cumsum(predicted_returns)
        max_return = np.max(cumulative_returns)
        final_return = cumulative_returns[-1]
        
        # 加入不确定性
        volatility_adj = std_return * np.sqrt(self.prediction_days)
        predicted_high_return = max_return + volatility_adj
        
        predicted_high = current_price * np.exp(predicted_high_return)
        expected_return = predicted_high_return
        
        # 计算置信度（基于模型拟合度）
        # 使用R平方衡量模型质量
        if len(returns) >= 10:
            x = np.arange(len(returns))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, returns)
            confidence = min(0.85, max(0.3, r_value ** 2))
        else:
            confidence = 0.4
        
        return {
            'predicted_high': predicted_high,
            'expected_return': expected_return,
            'confidence': confidence,
            'method': 'statistical_model',
            'details': {
                'mean_return': mean_return,
                'std_return': std_return,
                'lag1_correlation': lag1_corr,
                'volatility_adjustment': volatility_adj
            }
        }
    
    def _machine_learning_prediction(self, df: pd.DataFrame) -> Optional[Dict[str, float]]:
        """基于机器学习的预测"""
        if not SKLEARN_AVAILABLE:
            return None
        
        try:
            # 准备特征数据
            features = self._prepare_ml_features(df)
            if features is None or len(features) < 20:
                return None
            
            # 准备目标变量（未来N天的最高价）
            closes = df['Close'].values
            highs = df['High'].values
            
            # 创建滚动窗口的目标变量
            target_horizon = min(5, len(closes) // 4)  # 用较短的预测期训练
            X, y = [], []
            
            for i in range(len(features) - target_horizon):
                X.append(features[i])
                # 目标：未来target_horizon天内的最大收益率
                future_high = np.max(highs[i+1:i+1+target_horizon])
                current_price = closes[i]
                target_return = (future_high - current_price) / current_price
                y.append(target_return)
            
            if len(X) < 10:
                return None
            
            X = np.array(X)
            y = np.array(y)
            
            # 数据标准化
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # 训练模型
            model = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=5)
            model.fit(X_scaled, y)
            
            # 预测当前的目标
            current_features = features[-1].reshape(1, -1)
            current_features_scaled = scaler.transform(current_features)
            
            predicted_return = model.predict(current_features_scaled)[0]
            
            # 调整为14天预测（按比例放大）
            scaling_factor = self.prediction_days / target_horizon
            adjusted_return = predicted_return * scaling_factor
            
            current_price = closes[-1]
            predicted_high = current_price * (1 + adjusted_return)
            
            # 评估模型质量作为置信度
            train_pred = model.predict(X_scaled)
            mse = mean_squared_error(y, train_pred)
            confidence = min(0.9, max(0.4, 1 / (1 + mse * 10)))
            
            return {
                'predicted_high': predicted_high,
                'expected_return': adjusted_return,
                'confidence': confidence,
                'method': 'machine_learning',
                'details': {
                    'model_type': 'RandomForest',
                    'training_samples': len(X),
                    'mse': mse,
                    'feature_count': len(features[-1])
                }
            }
            
        except Exception as e:
            logger.warning(f"机器学习预测失败: {e}")
            return None
    
    def _monte_carlo_simulation(self, df: pd.DataFrame, n_simulations: int = 1000) -> Dict[str, float]:
        """蒙特卡洛模拟预测"""
        closes = df['Close'].values
        returns = np.diff(np.log(closes))
        
        if len(returns) < 10:
            return {
                'predicted_high': closes[-1] * 1.01,
                'expected_return': 0.01,
                'confidence': 0.3,
                'method': 'monte_carlo_fallback'
            }
        
        # 估计收益率分布参数
        mu = np.mean(returns)
        sigma = np.std(returns)
        
        # 考虑GARCH效应（简化版）
        volatility_clustering = self._estimate_volatility_clustering(returns)
        adjusted_sigma = sigma * (1 + volatility_clustering)
        
        # 蒙特卡洛模拟
        current_price = closes[-1]
        simulation_results = []
        
        for _ in range(n_simulations):
            # 生成未来14天的价格路径
            random_returns = np.random.normal(mu, adjusted_sigma, self.prediction_days)
            
            # 价格路径
            price_path = [current_price]
            for daily_return in random_returns:
                price_path.append(price_path[-1] * np.exp(daily_return))
            
            # 记录最高价
            max_price = max(price_path[1:])  # 排除当前价格
            max_return = (max_price - current_price) / current_price
            simulation_results.append(max_return)
        
        # 统计结果
        simulation_results = np.array(simulation_results)
        expected_return = np.mean(simulation_results)
        return_std = np.std(simulation_results)
        
        # 计算置信区间
        percentile_75 = np.percentile(simulation_results, 75)
        predicted_high = current_price * (1 + percentile_75)  # 使用75分位数
        
        # 置信度基于模拟结果的稳定性
        confidence = min(0.8, max(0.4, 1 / (1 + return_std * 5)))
        
        return {
            'predicted_high': predicted_high,
            'expected_return': expected_return,
            'confidence': confidence,
            'method': 'monte_carlo',
            'details': {
                'simulations': n_simulations,
                'return_std': return_std,
                'percentile_75': percentile_75,
                'volatility_clustering': volatility_clustering
            }
        }
    
    def _prepare_ml_features(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """准备机器学习特征"""
        if not SKLEARN_AVAILABLE:
            return None
        
        try:
            closes = df['Close'].values
            highs = df['High'].values
            lows = df['Low'].values
            volumes = df['Volume'].values
            
            features_list = []
            window_size = 20
            
            for i in range(window_size, len(closes)):
                window_close = closes[i-window_size:i]
                window_high = highs[i-window_size:i]
                window_low = lows[i-window_size:i]
                window_volume = volumes[i-window_size:i]
                
                # 价格特征
                returns = np.diff(np.log(window_close))
                mean_return = np.mean(returns)
                std_return = np.std(returns)
                
                # 技术指标特征
                ma5 = np.mean(window_close[-5:])
                ma20 = np.mean(window_close)
                ma_ratio = ma5 / ma20
                
                # 波动率特征
                high_low_ratio = np.mean(window_high / window_low)
                
                # 成交量特征
                volume_ma = np.mean(window_volume)
                recent_volume = np.mean(window_volume[-3:])
                volume_ratio = recent_volume / volume_ma
                
                # RSI
                gains = np.where(returns > 0, returns, 0)
                losses = np.where(returns < 0, -returns, 0)
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                rsi = 100 - (100 / (1 + avg_gain / (avg_loss + 1e-8)))
                
                # 相对位置
                current_price = window_close[-1]
                highest = np.max(window_high)
                lowest = np.min(window_low)
                price_position = (current_price - lowest) / (highest - lowest + 1e-8)
                
                # 组合特征
                feature_vector = [
                    mean_return, std_return, ma_ratio, high_low_ratio,
                    volume_ratio, rsi / 100, price_position,
                    # 添加滞后特征
                    returns[-1], returns[-2] if len(returns) > 1 else 0,
                    # 趋势特征
                    (window_close[-1] - window_close[0]) / window_close[0]
                ]
                
                features_list.append(feature_vector)
            
            return np.array(features_list) if features_list else None
            
        except Exception as e:
            logger.warning(f"特征准备失败: {e}")
            return None
    
    def _calculate_support_resistance(self, df: pd.DataFrame) -> Dict[str, float]:
        """计算支撑阻力位"""
        highs = df['High'].values
        lows = df['Low'].values
        current_price = df['Close'].iloc[-1]
        
        # 简单的支撑阻力位计算
        recent_highs = highs[-20:]
        recent_lows = lows[-20:]
        
        # 找出重要的高低点
        resistance_levels = []
        support_levels = []
        
        for i in range(2, len(recent_highs) - 2):
            # 局部最高点
            if (recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i-2] and
                recent_highs[i] > recent_highs[i+1] and recent_highs[i] > recent_highs[i+2]):
                resistance_levels.append(recent_highs[i])
            
            # 局部最低点
            if (recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i-2] and
                recent_lows[i] < recent_lows[i+1] and recent_lows[i] < recent_lows[i+2]):
                support_levels.append(recent_lows[i])
        
        # 找到最近的支撑阻力位
        resistance_above = [r for r in resistance_levels if r > current_price]
        support_below = [s for s in support_levels if s < current_price]
        
        nearest_resistance = min(resistance_above) if resistance_above else current_price * 1.05
        nearest_support = max(support_below) if support_below else current_price * 0.95
        
        return {
            'nearest_resistance': nearest_resistance,
            'nearest_support': nearest_support,
            'resistance_levels': resistance_levels,
            'support_levels': support_levels
        }
    
    def _estimate_volatility_clustering(self, returns: np.ndarray) -> float:
        """估计波动率聚集效应"""
        if len(returns) < 20:
            return 0.0
        
        # 计算滚动波动率
        window = 10
        rolling_vol = []
        for i in range(window, len(returns)):
            vol = np.std(returns[i-window:i])
            rolling_vol.append(vol)
        
        if len(rolling_vol) < 5:
            return 0.0
        
        # 波动率的自相关（简化的GARCH效应）
        vol_changes = np.diff(rolling_vol)
        if len(vol_changes) > 1:
            vol_autocorr = np.corrcoef(vol_changes[1:], vol_changes[:-1])[0, 1]
            return abs(vol_autocorr) if not np.isnan(vol_autocorr) else 0.0
        
        return 0.0
    
    def _calculate_prediction_weights(self, df: pd.DataFrame, predictions: List[Dict]) -> List[float]:
        """计算各预测方法的权重"""
        if not predictions:
            return []
        
        # 基础权重
        method_weights = {
            'technical_analysis': 0.3,
            'statistical_model': 0.25,
            'machine_learning': 0.35,
            'monte_carlo': 0.25
        }
        
        # 根据各方法的置信度调整权重
        weights = []
        total_confidence = sum(pred.get('confidence', 0.5) for pred in predictions)
        
        for pred in predictions:
            method = pred.get('method', 'unknown')
            base_weight = method_weights.get(method, 0.2)
            confidence = pred.get('confidence', 0.5)
            
            # 置信度加权
            adjusted_weight = base_weight * (confidence / (total_confidence / len(predictions)))
            weights.append(adjusted_weight)
        
        # 归一化权重
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        else:
            weights = [1.0 / len(predictions)] * len(predictions)
        
        return weights


class ReturnPredictionFactor(BaseFactor):
    """收益率预测因子"""
    
    def __init__(self):
        super().__init__(
            name="return_prediction_14d",
            category="prediction", 
            description="基于多种方法预测未来14天的收益率分布"
        )
        self.dependencies = ["price", "volume"]
        self.lookback_days = 50
        self.prediction_days = 14
    
    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算收益率预测因子"""
        # 获取价格数据
        price_df = data["price"].tail(self.lookback_days).copy()
        volume_df = data["volume"].tail(self.lookback_days).copy()
        
        min_len = min(len(price_df), len(volume_df))
        if min_len < 20:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)
        
        df = price_df.tail(min_len).copy()
        df['Volume'] = volume_df.tail(min_len)['Volume'].values
        
        # 计算收益率预测
        return_prediction = self._calculate_return_distribution(df)
        
        # 因子值为预期收益率
        factor_value = return_prediction['expected_return']
        
        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=factor_value,
            timestamp=datetime.now(),
            confidence=return_prediction['prediction_confidence'],
            raw_data=return_prediction
        )
    
    def _calculate_return_distribution(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算收益率分布预测"""
        closes = df['Close'].values
        returns = np.diff(np.log(closes))
        
        # 方法1: 历史分布外推
        historical_dist = self._analyze_historical_distribution(returns)
        
        # 方法2: 风险模型预测
        risk_model = self._risk_model_prediction(df)
        
        # 方法3: 动量因子预测
        momentum_prediction = self._momentum_based_prediction(df)
        
        # 综合预测
        predictions = [historical_dist, risk_model, momentum_prediction]
        weights = [0.4, 0.3, 0.3]
        
        expected_return = sum(pred['expected_return'] * w for pred, w in zip(predictions, weights))
        return_std = sum(pred['return_std'] * w for pred, w in zip(predictions, weights))
        confidence = sum(pred['confidence'] * w for pred, w in zip(predictions, weights))
        
        # 计算分位数
        percentiles = {
            '5%': expected_return - 1.645 * return_std,
            '25%': expected_return - 0.674 * return_std,
            '75%': expected_return + 0.674 * return_std,
            '95%': expected_return + 1.645 * return_std
        }
        
        return {
            'expected_return': expected_return,
            'return_std': return_std,
            'prediction_confidence': confidence,
            'percentiles': percentiles,
            'individual_predictions': predictions,
            'prediction_weights': weights
        }
    
    def _analyze_historical_distribution(self, returns: np.ndarray) -> Dict[str, float]:
        """分析历史收益率分布"""
        if len(returns) < 10:
            return {'expected_return': 0.0, 'return_std': 0.02, 'confidence': 0.3}
        
        # 基本统计量
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # 扩展到14天期间
        period_return = mean_return * self.prediction_days
        period_std = std_return * np.sqrt(self.prediction_days)
        
        # 置信度基于样本数量
        confidence = min(0.8, len(returns) / 50)
        
        return {
            'expected_return': period_return,
            'return_std': period_std,
            'confidence': confidence
        }
    
    def _risk_model_prediction(self, df: pd.DataFrame) -> Dict[str, float]:
        """基于风险模型的预测"""
        closes = df['Close'].values
        volumes = df['Volume'].values
        returns = np.diff(np.log(closes))
        
        if len(returns) < 15:
            return {'expected_return': 0.0, 'return_std': 0.02, 'confidence': 0.3}
        
        # 计算风险指标
        # VaR 风险值
        var_95 = np.percentile(returns, 5)  # 5%分位数
        
        # 波动率衰减模型
        decay_factor = 0.94
        weights = np.array([decay_factor ** i for i in range(len(returns))][::-1])
        weights = weights / np.sum(weights)
        
        weighted_mean = np.sum(returns * weights)
        weighted_var = np.sum(weights * (returns - weighted_mean) ** 2)
        weighted_std = np.sqrt(weighted_var)
        
        # 流动性调整
        liquidity_factor = self._calculate_liquidity_factor(volumes)
        
        # 风险调整后的预期收益
        risk_adjusted_return = weighted_mean * (1 + liquidity_factor)
        risk_adjusted_std = weighted_std * (1 + abs(liquidity_factor) * 0.5)
        
        # 扩展到14天
        period_return = risk_adjusted_return * self.prediction_days
        period_std = risk_adjusted_std * np.sqrt(self.prediction_days)
        
        confidence = 0.7  # 风险模型通常比较稳定
        
        return {
            'expected_return': period_return,
            'return_std': period_std,
            'confidence': confidence
        }
    
    def _momentum_based_prediction(self, df: pd.DataFrame) -> Dict[str, float]:
        """基于动量的预测"""
        closes = df['Close'].values
        volumes = df['Volume'].values
        
        if len(closes) < 20:
            return {'expected_return': 0.0, 'return_std': 0.02, 'confidence': 0.3}
        
        # 计算多时间框架动量
        momentum_3d = (closes[-1] / closes[-4] - 1) if len(closes) >= 4 else 0
        momentum_5d = (closes[-1] / closes[-6] - 1) if len(closes) >= 6 else 0
        momentum_10d = (closes[-1] / closes[-11] - 1) if len(closes) >= 11 else 0
        momentum_20d = (closes[-1] / closes[-21] - 1) if len(closes) >= 21 else 0
        
        # 动量衰减模型
        momentum_scores = [momentum_3d, momentum_5d, momentum_10d, momentum_20d]
        momentum_weights = [0.4, 0.3, 0.2, 0.1]  # 近期动量权重更高
        
        weighted_momentum = sum(score * weight for score, weight in zip(momentum_scores, momentum_weights))
        
        # 成交量确认
        volume_confirmation = self._calculate_volume_confirmation(volumes)
        
        # 预测收益率
        momentum_return = weighted_momentum * 0.5 * volume_confirmation  # 动量延续性
        
        # 动量标准差
        momentum_std = np.std([m for m in momentum_scores if m != 0]) if any(momentum_scores) else 0.02
        
        # 扩展到14天（动量通常不会完全持续）
        decay_factor = 0.8  # 动量衰减
        period_return = momentum_return * self.prediction_days * decay_factor
        period_std = momentum_std * np.sqrt(self.prediction_days)
        
        # 置信度基于动量一致性
        momentum_consistency = 1 - np.std([abs(m) for m in momentum_scores if m != 0])
        confidence = min(0.8, max(0.4, momentum_consistency))
        
        return {
            'expected_return': period_return,
            'return_std': period_std,
            'confidence': confidence
        }
    
    def _calculate_liquidity_factor(self, volumes: np.ndarray) -> float:
        """计算流动性因子"""
        if len(volumes) < 10:
            return 0.0
        
        # 成交量变化率
        volume_changes = np.diff(volumes)
        volume_volatility = np.std(volume_changes) / np.mean(volumes)
        
        # 流动性因子：负值表示流动性不足带来的额外风险
        liquidity_factor = -min(0.1, volume_volatility)
        
        return liquidity_factor
    
    def _calculate_volume_confirmation(self, volumes: np.ndarray) -> float:
        """计算成交量确认因子"""
        if len(volumes) < 5:
            return 1.0
        
        recent_volume = np.mean(volumes[-3:])
        historical_volume = np.mean(volumes[:-3])
        
        if historical_volume > 0:
            volume_ratio = recent_volume / historical_volume
            # 成交量放大确认动量，成交量萎缩减弱动量
            return min(1.5, max(0.5, volume_ratio))
        
        return 1.0


# 注册预测因子的函数
def register_prediction_factors():
    """注册所有预测因子"""
    from .factor_manager import get_factor_manager
    
    factor_manager = get_factor_manager()
    
    # 注册价格预测因子
    factor_manager.register_factor(PricePredictionFactor())
    
    # 注册收益率预测因子
    factor_manager.register_factor(ReturnPredictionFactor())
    
    logger.info("预测因子注册完成")