#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重置Qlib因子状态脚本
在同步Qlib数据后，清除Qlib因子的禁用状态，让它们重新参与IC评估
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reset_qlib_factors():
    """重置Qlib因子权重和禁用状态"""

    weights_file = 'factor_cache/factor_weights.json'

    if not os.path.exists(weights_file):
        logger.error(f"权重文件不存在: {weights_file}")
        return False

    # 1. 读取当前权重文件
    logger.info("读取当前权重文件...")
    with open(weights_file, 'r', encoding='utf-8') as f:
        weights_data = json.load(f)

    # 2. 统计Qlib因子
    qlib_factors = [name for name in weights_data['weights'].keys()
                    if name.startswith('qlib_')]
    disabled_qlib = [name for name in weights_data.get('disabled', [])
                     if name.startswith('qlib_')]

    logger.info(f"总因子数: {len(weights_data['weights'])}")
    logger.info(f"Qlib因子数: {len(qlib_factors)}")
    logger.info(f"被禁用的Qlib因子: {len(disabled_qlib)}")

    # 3. 重置Qlib因子权重为默认值1.0
    logger.info("\n重置Qlib因子权重为1.0...")
    reset_count = 0
    for factor_name in qlib_factors:
        if weights_data['weights'][factor_name] == 0.0:
            weights_data['weights'][factor_name] = 1.0
            reset_count += 1

    logger.info(f"重置了 {reset_count} 个Qlib因子的权重")

    # 4. 从禁用列表中移除Qlib因子
    logger.info("\n从禁用列表中移除Qlib因子...")
    if 'disabled' in weights_data:
        original_disabled_count = len(weights_data['disabled'])
        weights_data['disabled'] = [name for name in weights_data['disabled']
                                     if not name.startswith('qlib_')]
        removed_count = original_disabled_count - len(weights_data['disabled'])
        logger.info(f"移除了 {removed_count} 个Qlib因子")

    # 5. 更新时间戳
    weights_data['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 6. 备份原文件
    backup_file = weights_file + '.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    logger.info(f"\n备份原文件到: {backup_file}")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(weights_data, f, indent=2, ensure_ascii=False)

    # 7. 保存更新后的文件
    logger.info(f"保存更新后的权重文件...")
    with open(weights_file, 'w', encoding='utf-8') as f:
        json.dump(weights_data, f, indent=2, ensure_ascii=False)

    # 8. 显示结果
    logger.info("\n" + "="*60)
    logger.info("重置完成！")
    logger.info("="*60)
    logger.info(f"Qlib因子权重: 0.0 -> 1.0 ({reset_count}个)")
    logger.info(f"从禁用列表移除: {removed_count}个")
    logger.info(f"当前禁用因子总数: {len(weights_data['disabled'])}")

    # 9. 下一步提示
    logger.info("\n" + "="*60)
    logger.info("下一步操作:")
    logger.info("="*60)
    logger.info("1. 确保已运行 sync_qlib_data.py 同步数据")
    logger.info("2. 运行 main.py 进行股票分析（50次后触发IC评估）")
    logger.info("3. 或运行历史回测快速触发IC评估")
    logger.info("4. Qlib因子将基于真实数据重新评估")
    logger.info("5. 高IC因子会获得更高权重，低IC因子会再次被禁用")

    return True

def main():
    """主函数"""
    logger.info("="*60)
    logger.info("Qlib因子重置脚本")
    logger.info("="*60)

    try:
        success = reset_qlib_factors()
        if success:
            logger.info("\n[OK] 重置成功！")
            return 0
        else:
            logger.error("\n[FAIL] 重置失败")
            return 1
    except Exception as e:
        logger.error(f"\n[FAIL] 重置失败: {e}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
