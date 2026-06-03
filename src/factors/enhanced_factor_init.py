# -*- coding: utf-8 -*-
"""
增强因子系统初始化
注册所有新因子并启用动态权重优化
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def initialize_enhanced_factor_system(enable_auto_weight_optimization: bool = True) -> Dict:
    """
    初始化增强因子系统

    Args:
        enable_auto_weight_optimization: 是否启用自动权重优化

    Returns:
        初始化结果字典
    """

    logger.info("="*60)
    logger.info("🚀 初始化增强因子系统")
    logger.info("="*60)

    results = {
        'registered_factors': [],
        'failed_factors': [],
        'total_count': 0,
        'dynamic_weight_enabled': enable_auto_weight_optimization
    }

    try:
        from src.factors.factor_manager import get_factor_manager

        factor_manager = get_factor_manager()

        # 注册增强动量因子 (4个)
        try:
            from src.factors.momentum_enhanced_factors import register_momentum_enhanced_factors
            register_momentum_enhanced_factors()
            results['registered_factors'].extend([
                'acceleration_momentum',
                'gap_strength',
                'trend_persistence',
                'historical_percentile'
            ])
            logger.info("✅ 增强动量因子注册成功 (4个)")
        except Exception as e:
            logger.error(f"❌ 增强动量因子注册失败: {e}")
            results['failed_factors'].append('momentum_enhanced')

        # 注册市场微观结构因子 (3个)
        try:
            from src.factors.microstructure_factors import register_microstructure_factors
            register_microstructure_factors()
            results['registered_factors'].extend([
                'big_order_flow',
                'bid_ask_ratio',
                'intraday_volume_ratio'
            ])
            logger.info("✅ 市场微观结构因子注册成功 (3个)")
        except Exception as e:
            logger.error(f"❌ 市场微观结构因子注册失败: {e}")
            results['failed_factors'].append('microstructure')

        # 注册情绪因子 (3个)
        try:
            from src.factors.sentiment_factors import register_sentiment_factors
            register_sentiment_factors()
            results['registered_factors'].extend([
                'longhu_sentiment',
                'social_media_buzz',
                'sector_momentum'
            ])
            logger.info("✅ 情绪因子注册成功 (3个，支持代理数据)")
        except Exception as e:
            logger.error(f"❌ 情绪因子注册失败: {e}")
            results['failed_factors'].append('sentiment')

        # 注册基础技术因子（如果还未注册）
        try:
            from src.factors.technical_ai_factors import register_technical_ai_factors
            register_technical_ai_factors()
            logger.info("✅ 基础技术因子已加载")
        except Exception as e:
            logger.warning(f"基础技术因子注册跳过: {e}")

        # 统计
        results['total_count'] = len(results['registered_factors'])

        logger.info("\n📊 因子注册统计:")
        logger.info(f"  成功注册: {results['total_count']} 个因子")
        if results['failed_factors']:
            logger.warning(f"  注册失败: {len(results['failed_factors'])} 类")

        # 启用动态权重优化
        if enable_auto_weight_optimization:
            logger.info("\n⚙️ 启用动态权重优化系统...")

            if factor_manager.enable_auto_evaluation:
                logger.info("  ✅ IC评估系统已启用")
                logger.info("  ✅ 自动权重调整已启用")
                logger.info("  ✅ 因子淘汰机制已启用")

                # 显示当前权重配置
                if factor_manager.factor_weights:
                    logger.info("\n📊 当前因子权重:")
                    for factor_name, weight in sorted(
                        factor_manager.factor_weights.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:10]:  # 显示前10个
                        status = "❌" if factor_name in factor_manager.disabled_factors else "✅"
                        logger.info(f"  {status} {factor_name}: {weight:.3f}")
            else:
                logger.warning("  ⚠️ IC评估系统未启用（缺少依赖）")

        logger.info("\n" + "="*60)
        logger.info("🎉 增强因子系统初始化完成！")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"因子系统初始化失败: {e}")
        results['error'] = str(e)

    return results


def get_factor_summary() -> Dict:
    """获取因子系统摘要"""
    try:
        from src.factors.factor_manager import get_factor_manager

        factor_manager = get_factor_manager()

        summary = {
            'total_count': len(factor_manager.factors),  # 修改为 total_count 以保持一致
            'total_factors': len(factor_manager.factors),
            'active_factors': len(factor_manager.factors) - len(factor_manager.disabled_factors),
            'disabled_factors': len(factor_manager.disabled_factors),
            'dynamic_weight_enabled': factor_manager.enable_auto_evaluation,
            'analysis_count': factor_manager.analysis_count,
            'factors_by_category': {}
        }

        # 按类别统计
        for factor in factor_manager.factors.values():
            category = factor.category
            if category not in summary['factors_by_category']:
                summary['factors_by_category'][category] = []
            summary['factors_by_category'][category].append(factor.name)

        return summary

    except Exception as e:
        logger.error(f"获取因子摘要失败: {e}")
        return {}


def print_factor_health_report():
    """打印因子健康报告"""
    try:
        from src.factors.factor_manager import get_factor_manager

        factor_manager = get_factor_manager()

        if not factor_manager.enable_auto_evaluation:
            logger.info("动态评估未启用，跳过健康报告")
            return

        health = factor_manager.get_factor_health_summary()

        logger.info("\n" + "="*60)
        logger.info("📋 因子健康报告")
        logger.info("="*60)
        logger.info(f"总因子数: {health['total_factors']}")
        logger.info(f"已禁用: {health['disabled_factors']}")
        logger.info(f"分析次数: {health['analysis_count']}")
        logger.info(f"数据天数: {health['data_days']}")
        logger.info(f"上次评估: {health['last_evaluation']}")

        logger.info("\n📊 因子评级:")
        for factor_name, info in health['factors'].items():
            status = "❌" if info['disabled'] else "✅"
            logger.info(f"  {status} {factor_name}: {info['rating']} (权重={info['weight']:.2f})")

        logger.info("="*60)

    except Exception as e:
        logger.error(f"打印健康报告失败: {e}")


# 便捷函数
def enable_all_new_factors():
    """快速启用所有新因子"""
    return initialize_enhanced_factor_system(enable_auto_weight_optimization=True)


def disable_factor_by_name(factor_name: str):
    """手动禁用指定因子"""
    try:
        from src.factors.factor_manager import get_factor_manager

        factor_manager = get_factor_manager()
        factor_manager.disabled_factors.add(factor_name)
        factor_manager._save_factor_weights()

        logger.info(f"已禁用因子: {factor_name}")

    except Exception as e:
        logger.error(f"禁用因子失败: {e}")


def reset_factor_weights():
    """重置所有因子权重为均等"""
    try:
        from src.factors.factor_manager import get_factor_manager

        factor_manager = get_factor_manager()
        factor_manager._initialize_default_weights()
        factor_manager._save_factor_weights()

        logger.info("已重置所有因子权重为均等")

    except Exception as e:
        logger.error(f"重置权重失败: {e}")
