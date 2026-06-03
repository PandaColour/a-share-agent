# -*- coding: utf-8 -*-
"""
因子监控模块
用于持续监控因子健康状况，触发预警，自动淘汰失效因子
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class FactorMonitor:
    """因子监控器"""

    def __init__(self,
                 ic_evaluator,
                 alert_config: Dict = None):
        """
        初始化因子监控器

        Args:
            ic_evaluator: IC评估器实例
            alert_config: 预警配置
        """
        self.ic_evaluator = ic_evaluator
        self.alert_history = {}  # {factor_name: [alerts]}
        self.disabled_factors = set()  # 已禁用的因子

        # 默认预警配置
        self.alert_config = alert_config or {
            'yellow': {
                'ic_drop_pct': 0.20,  # IC下降20%
                'consecutive_low_ic_days': 5,  # 连续5天低IC
                'low_ic_threshold': 0.03
            },
            'orange': {
                'ic_drop_pct': 0.40,  # IC下降40%
                'consecutive_low_ic_days': 10,  # 连续10天低IC
                'low_ic_threshold': 0.02
            },
            'red': {
                'negative_ic_days': 3,  # 连续3天负IC
                'ic_threshold': -0.01,  # IC<-0.01
                'consecutive_low_ic_days': 20,  # 连续20天IC<0.01
                'low_ic_threshold': 0.01
            }
        }

        logger.info("因子监控器初始化完成")

    def check_factor_health(self, factor_name: str, window: int = 20) -> Dict:
        """
        检查因子健康状况

        Args:
            factor_name: 因子名称
            window: 检查窗口（天数）

        Returns:
            健康状况字典
        """
        # 获取IC历史
        if factor_name not in self.ic_evaluator.ic_history:
            return {
                'status': 'unknown',
                'message': '无IC历史数据'
            }

        ic_data = self.ic_evaluator.ic_history[factor_name]
        dates = sorted(ic_data.keys())

        if len(dates) < window:
            return {
                'status': 'insufficient_data',
                'message': f'数据不足{window}天'
            }

        # 取最近window天的IC
        recent_dates = dates[-window:]
        recent_ic = [ic_data[date]['ic'] for date in recent_dates]

        # 计算统计
        current_ic = recent_ic[-1]
        avg_ic = sum(recent_ic) / len(recent_ic)

        # 获取历史基准IC（前一个window的平均）
        if len(dates) >= window * 2:
            baseline_dates = dates[-window*2:-window]
            baseline_ic = [ic_data[date]['ic'] for date in baseline_dates]
            baseline_avg = sum(baseline_ic) / len(baseline_ic)
        else:
            baseline_avg = avg_ic

        # 检查各种预警条件
        alerts = []

        # 1. 检查IC下降
        if baseline_avg > 0:
            ic_drop = (baseline_avg - avg_ic) / baseline_avg

            if ic_drop >= self.alert_config['red']['ic_drop_pct']:
                alerts.append({
                    'level': 'red',
                    'type': 'ic_drop',
                    'message': f'IC下降{ic_drop:.1%}（严重）',
                    'value': ic_drop
                })
            elif ic_drop >= self.alert_config['orange']['ic_drop_pct']:
                alerts.append({
                    'level': 'orange',
                    'type': 'ic_drop',
                    'message': f'IC下降{ic_drop:.1%}（警告）',
                    'value': ic_drop
                })
            elif ic_drop >= self.alert_config['yellow']['ic_drop_pct']:
                alerts.append({
                    'level': 'yellow',
                    'type': 'ic_drop',
                    'message': f'IC下降{ic_drop:.1%}（关注）',
                    'value': ic_drop
                })

        # 2. 检查连续负IC
        consecutive_negative = 0
        for ic in reversed(recent_ic):
            if ic < 0:
                consecutive_negative += 1
            else:
                break

        if consecutive_negative >= self.alert_config['red']['negative_ic_days']:
            alerts.append({
                'level': 'red',
                'type': 'negative_ic',
                'message': f'连续{consecutive_negative}天负IC',
                'value': consecutive_negative
            })

        # 3. 检查连续低IC
        for level in ['red', 'orange', 'yellow']:
            threshold = self.alert_config[level]['low_ic_threshold']
            required_days = self.alert_config[level]['consecutive_low_ic_days']

            consecutive_low = 0
            for ic in reversed(recent_ic):
                if ic < threshold:
                    consecutive_low += 1
                else:
                    break

            if consecutive_low >= required_days:
                alerts.append({
                    'level': level,
                    'type': 'low_ic',
                    'message': f'连续{consecutive_low}天IC<{threshold}',
                    'value': consecutive_low
                })
                break

        # 确定总体状态
        if any(a['level'] == 'red' for a in alerts):
            status = 'critical'
        elif any(a['level'] == 'orange' for a in alerts):
            status = 'warning'
        elif any(a['level'] == 'yellow' for a in alerts):
            status = 'caution'
        else:
            status = 'healthy'

        return {
            'status': status,
            'current_ic': current_ic,
            'avg_ic': avg_ic,
            'baseline_ic': baseline_avg,
            'alerts': alerts,
            'check_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def monitor_all_factors(self, factor_names: List[str]) -> Dict[str, Dict]:
        """
        监控所有因子

        Args:
            factor_names: 因子名称列表

        Returns:
            监控结果字典
        """
        logger.info(f"开始监控 {len(factor_names)} 个因子...")

        results = {}
        critical_factors = []
        warning_factors = []

        for factor_name in factor_names:
            health = self.check_factor_health(factor_name)
            results[factor_name] = health

            if health['status'] == 'critical':
                critical_factors.append(factor_name)
            elif health['status'] == 'warning':
                warning_factors.append(factor_name)

        # 记录预警
        if critical_factors:
            logger.warning(f"🔴 严重预警 ({len(critical_factors)}个): {', '.join(critical_factors)}")

        if warning_factors:
            logger.warning(f"🟠 警告预警 ({len(warning_factors)}个): {', '.join(warning_factors)}")

        logger.info(f"监控完成")
        return results

    def auto_disable_factor(self, factor_name: str, reason: str):
        """
        自动禁用因子

        Args:
            factor_name: 因子名称
            reason: 禁用原因
        """
        self.disabled_factors.add(factor_name)

        # 记录
        logger.warning(f"⚠️ 自动禁用因子: {factor_name}")
        logger.warning(f"   原因: {reason}")

        # 保存禁用记录
        self._save_disabled_log(factor_name, reason)

    def handle_critical_alerts(self, monitor_results: Dict[str, Dict]):
        """
        处理严重预警（自动禁用）

        Args:
            monitor_results: 监控结果
        """
        for factor_name, health in monitor_results.items():
            if health['status'] != 'critical':
                continue

            if factor_name in self.disabled_factors:
                continue

            # 检查是否触发自动禁用条件
            alerts = health['alerts']

            for alert in alerts:
                if alert['level'] == 'red':
                    # 触发自动禁用
                    self.auto_disable_factor(factor_name, alert['message'])
                    break

    def generate_monitor_report(self, monitor_results: Dict[str, Dict]) -> str:
        """
        生成监控报告

        Args:
            monitor_results: 监控结果

        Returns:
            报告文本（Markdown格式）
        """
        report = []
        report.append("# 因子监控报告\n")
        report.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"**监控因子数**: {len(monitor_results)}\n\n")

        # 统计
        status_count = {'healthy': 0, 'caution': 0, 'warning': 0, 'critical': 0, 'unknown': 0}

        for health in monitor_results.values():
            status = health.get('status', 'unknown')
            if status in status_count:
                status_count[status] += 1

        report.append("## 📊 健康状况统计\n")
        report.append(f"- ✅ 健康: {status_count['healthy']}个\n")
        report.append(f"- 🟡 关注: {status_count['caution']}个\n")
        report.append(f"- 🟠 警告: {status_count['warning']}个\n")
        report.append(f"- 🔴 严重: {status_count['critical']}个\n")
        report.append(f"- ❓ 未知: {status_count['unknown']}个\n\n")

        # 详细报告
        # 按严重程度排序
        sorted_results = sorted(
            monitor_results.items(),
            key=lambda x: {
                'critical': 4,
                'warning': 3,
                'caution': 2,
                'healthy': 1,
                'unknown': 0
            }.get(x[1].get('status', 'unknown'), 0),
            reverse=True
        )

        report.append("## 📋 详细监控结果\n\n")

        for factor_name, health in sorted_results:
            status = health.get('status', 'unknown')

            # 状态emoji
            status_emoji = {
                'critical': '🔴',
                'warning': '🟠',
                'caution': '🟡',
                'healthy': '✅',
                'unknown': '❓'
            }.get(status, '❓')

            report.append(f"### {status_emoji} {factor_name}\n")
            report.append(f"- **状态**: {status}\n")

            if 'current_ic' in health:
                report.append(f"- **当前IC**: {health['current_ic']:.4f}\n")
                report.append(f"- **平均IC**: {health['avg_ic']:.4f}\n")
                report.append(f"- **基准IC**: {health['baseline_ic']:.4f}\n")

            # 预警信息
            if 'alerts' in health and health['alerts']:
                report.append("- **预警**:\n")
                for alert in health['alerts']:
                    level_emoji = {'red': '🔴', 'orange': '🟠', 'yellow': '🟡'}.get(alert['level'], '')
                    report.append(f"  - {level_emoji} {alert['message']}\n")

            report.append("\n")

        # 已禁用因子
        if self.disabled_factors:
            report.append("## ⛔ 已禁用因子\n\n")
            for factor in self.disabled_factors:
                report.append(f"- {factor}\n")
            report.append("\n")

        return "".join(report)

    def _save_disabled_log(self, factor_name: str, reason: str):
        """保存禁用日志"""
        log_dir = Path("factor_cache/disabled_factors")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "disabled_log.json"

        # 加载现有日志
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                disabled_log = json.load(f)
        else:
            disabled_log = []

        # 添加新记录
        disabled_log.append({
            'factor_name': factor_name,
            'reason': reason,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        # 保存
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(disabled_log, f, indent=2, ensure_ascii=False)

    def daily_health_check(self, factor_names: List[str]) -> str:
        """
        每日健康检查（主要接口）

        Args:
            factor_names: 因子名称列表

        Returns:
            报告文件路径
        """
        logger.info("\n" + "="*60)
        logger.info("每日因子健康检查")
        logger.info("="*60)

        # 监控所有因子
        results = self.monitor_all_factors(factor_names)

        # 处理严重预警
        self.handle_critical_alerts(results)

        # 生成报告
        report = self.generate_monitor_report(results)

        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d')
        report_dir = Path("factor_cache/monitor_reports")
        report_dir.mkdir(parents=True, exist_ok=True)

        report_file = report_dir / f"monitor_report_{timestamp}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"✓ 监控报告已保存: {report_file}")

        return str(report_file)
