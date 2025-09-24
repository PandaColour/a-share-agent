# -*- coding: utf-8 -*-
"""机器学习预测模型客户端"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from .base import AIModelInterface

logger = logging.getLogger(__name__)


class MLPredictionClient(AIModelInterface):
    """机器学习预测模型客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_type = config.get("model_type", "random_forest")
        self.prediction_horizon = config.get("prediction_horizon", 14)

        # 可选依赖的导入
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.linear_model import LinearRegression
            from sklearn.svm import SVR
            self.sklearn_available = True
        except ImportError:
            logger.warning("scikit-learn未安装，机器学习预测模型不可用")
            self.sklearn_available = False

    def generate_analysis(self, prompt: str, context: Dict = None) -> str:
        """生成机器学习预测分析"""
        if not self.is_available():
            return "机器学习模型不可用，请安装scikit-learn"

        try:
            # 从上下文中提取预测数据
            if context and "prediction_data" in context:
                prediction_result = self._make_prediction(context["prediction_data"])
                return self._format_prediction_result(prediction_result, context)
            else:
                return "缺少预测所需的历史数据"

        except Exception as e:
            logger.error(f"机器学习预测失败: {e}")
            return f"预测模型分析失败: {str(e)}"

    def _make_prediction(self, data: Dict) -> Dict:
        """执行机器学习预测"""
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.preprocessing import StandardScaler
        import numpy as np
        import pandas as pd

        # 准备特征数据
        price_data = data.get("price_data", pd.DataFrame())
        volume_data = data.get("volume_data", pd.DataFrame())

        if price_data.empty:
            raise ValueError("缺少价格数据")

        # 构建特征
        features = self._build_features(price_data, volume_data)
        if len(features) < 20:
            raise ValueError("历史数据不足，需要至少20个交易日的数据")

        # 准备训练数据
        X, y = self._prepare_training_data(features, price_data)

        # 训练模型
        if self.model_type == "random_forest":
            model = RandomForestRegressor(n_estimators=100, random_state=42)
        elif self.model_type == "linear":
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
        else:
            model = RandomForestRegressor(n_estimators=50, random_state=42)

        # 数据标准化
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 训练模型
        model.fit(X_scaled, y)

        # 预测
        latest_features = features[-1].reshape(1, -1)
        latest_scaled = scaler.transform(latest_features)
        predicted_return = model.predict(latest_scaled)[0]

        current_price = price_data['Close'].iloc[-1]
        predicted_price = current_price * (1 + predicted_return)

        # 计算预测置信度
        if hasattr(model, 'predict'):
            train_pred = model.predict(X_scaled)
            mse = np.mean((y - train_pred) ** 2)
            confidence = max(0.3, min(0.9, 1 / (1 + mse * 10)))
        else:
            confidence = 0.6

        return {
            "predicted_return": predicted_return,
            "predicted_price": predicted_price,
            "current_price": current_price,
            "confidence": confidence,
            "model_type": self.model_type,
            "prediction_horizon": self.prediction_horizon
        }

    def _build_features(self, price_data: pd.DataFrame, volume_data: pd.DataFrame) -> np.ndarray:
        """构建机器学习特征"""
        import numpy as np

        closes = price_data['Close'].values
        highs = price_data['High'].values if 'High' in price_data.columns else closes
        lows = price_data['Low'].values if 'Low' in price_data.columns else closes
        volumes = volume_data['Volume'].values if not volume_data.empty else np.ones(len(closes))

        features_list = []

        for i in range(20, len(closes)):  # 需要20个历史点来计算特征
            window_close = closes[i-20:i]
            window_high = highs[i-20:i]
            window_low = lows[i-20:i]
            window_volume = volumes[i-20:i] if i < len(volumes) else np.ones(20)

            # 计算技术指标特征
            returns = np.diff(np.log(window_close))

            # 基础统计特征
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            skew_return = self._calculate_skewness(returns)

            # 移动平均特征
            ma5 = np.mean(window_close[-5:])
            ma10 = np.mean(window_close[-10:])
            ma20 = np.mean(window_close)

            # 相对强弱指标
            gains = np.where(returns > 0, returns, 0)
            losses = np.where(returns < 0, -returns, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            rsi = 100 - (100 / (1 + avg_gain / (avg_loss + 1e-8)))

            # 布林带位置
            bb_middle = ma20
            bb_std = np.std(window_close)
            bb_upper = bb_middle + 2 * bb_std
            bb_lower = bb_middle - 2 * bb_std
            bb_position = (window_close[-1] - bb_lower) / (bb_upper - bb_lower + 1e-8)

            # 价格位置
            highest = np.max(window_high)
            lowest = np.min(window_low)
            price_position = (window_close[-1] - lowest) / (highest - lowest + 1e-8)

            # 成交量特征
            volume_ma = np.mean(window_volume)
            volume_ratio = window_volume[-1] / (volume_ma + 1e-8)

            # 动量特征
            momentum_5 = (window_close[-1] / window_close[-6] - 1) if len(window_close) >= 6 else 0
            momentum_10 = (window_close[-1] / window_close[-11] - 1) if len(window_close) >= 11 else 0

            # 波动率特征
            volatility = std_return

            # 组合特征向量
            feature_vector = [
                mean_return, std_return, skew_return,
                ma5/ma20, ma10/ma20,
                rsi/100, bb_position, price_position,
                volume_ratio, momentum_5, momentum_10,
                volatility
            ]

            features_list.append(feature_vector)

        return np.array(features_list)

    def _prepare_training_data(self, features: np.ndarray, price_data: pd.DataFrame) -> tuple:
        """准备训练数据"""
        import numpy as np

        closes = price_data['Close'].values

        X = []
        y = []

        # 为每个特征向量，计算对应的未来收益率
        feature_start_idx = 20  # 特征从第20个数据点开始

        for i in range(len(features)):
            actual_price_idx = feature_start_idx + i

            # 确保有足够的未来数据点
            future_end_idx = actual_price_idx + self.prediction_horizon
            if future_end_idx < len(closes):
                current_price = closes[actual_price_idx]
                future_prices = closes[actual_price_idx+1:future_end_idx+1]
                max_future_price = np.max(future_prices)

                # 目标变量：未来期间的最大收益率
                target_return = (max_future_price - current_price) / current_price

                X.append(features[i])
                y.append(target_return)

        return np.array(X), np.array(y)

    def _calculate_skewness(self, data: np.ndarray) -> float:
        """计算偏度"""
        if len(data) < 3:
            return 0.0

        mean_val = np.mean(data)
        std_val = np.std(data)

        if std_val == 0:
            return 0.0

        skewness = np.mean(((data - mean_val) / std_val) ** 3)
        return skewness

    def _format_prediction_result(self, result: Dict, context: Dict) -> str:
        """格式化预测结果"""
        symbol = context.get("symbol", "股票")
        predicted_return = result["predicted_return"]
        predicted_price = result["predicted_price"]
        current_price = result["current_price"]
        confidence = result["confidence"]

        return_pct = predicted_return * 100
        price_change = predicted_price - current_price

        analysis = f"""机器学习预测分析 ({result['model_type']})：

📊 预测结果：
• 当前价格：¥{current_price:.2f}
• 预测{self.prediction_horizon}天内最高价：¥{predicted_price:.2f}
• 预期最大收益率：{return_pct:+.2f}%
• 价格变化：¥{price_change:+.2f}

🎯 预测置信度：{confidence*100:.1f}%

📈 投资建议：
"""

        if predicted_return > 0.05:
            analysis += "模型预测显示显著上涨潜力，建议关注买入机会。"
        elif predicted_return > 0.02:
            analysis += "模型预测温和上涨，可考虑适当配置。"
        elif predicted_return > -0.02:
            analysis += "模型预测价格相对稳定，建议持有观望。"
        else:
            analysis += "模型预测下跌风险，建议谨慎操作。"

        analysis += f"\n\n⚠️ 注意：预测结果基于历史数据训练，实际表现可能存在差异。"

        return analysis

    def is_available(self) -> bool:
        return self.sklearn_available