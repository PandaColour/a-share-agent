# -*- coding: utf-8 -*-
"""
买入/持有建议二次复核流程。

筛选原始买入/持有候选，聚合基本面和新闻数据，调用复核 Agent，并将结构化
复核结果合并回内存分析结果。
"""

import json
import logging
import shutil
import time
from importlib import import_module
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from src.agents.buy_confirmation_agent import (
        BUY_ACTION,
        HOLD_ACTION,
        SELL_ACTION,
        VALID_CANDIDATE_ACTIONS,
        VALID_FINAL_ACTIONS,
        BuyConfirmationAgent,
    )
except ImportError:
    from agents.buy_confirmation_agent import (
        BUY_ACTION,
        HOLD_ACTION,
        SELL_ACTION,
        VALID_CANDIDATE_ACTIONS,
        VALID_FINAL_ACTIONS,
        BuyConfirmationAgent,
    )

logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    "candidate_actions": [BUY_ACTION, HOLD_ACTION],
    "allowed_final_actions": [BUY_ACTION, HOLD_ACTION, SELL_ACTION],
    "max_workers": 2,
    "timeout_seconds": 60,
    "max_news": 6,
    "on_parse_failure": "hold",
    "write_backup": True,
    "hold_when_all_external_data_missing": False,
}


class BuyConfirmationProcess:
    """买入/持有二次复核编排流程。"""

    def __init__(self, config=None, output_dir: Optional[Path] = None):
        self.settings = self._load_settings()
        self.output_dir = Path(output_dir) if output_dir else None
        self.data_provider = None
        self.news_fetcher = None
        self.agent = self._create_agent()

    def execute(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        candidates = self._find_buy_candidates(results)
        if not candidates:
            logger.info("买入/持有二次复核跳过：无候选")
            return {"processed_count": 0, "review_results": []}

        try:
            self._ensure_collectors()
            review_results = self._review_candidates(candidates)
        except Exception as exc:
            reason = f"外部数据采集器初始化失败，按保守策略降级: {exc}"
            logger.warning(reason)
            review_results = [
                self._fallback_for_candidate(
                    candidate,
                    reason,
                    status="data_unavailable",
                    data_quality=self._collector_init_failure_quality(reason),
                )
                for candidate in candidates
            ]
        result_map = {item.get("symbol"): item for item in review_results}

        for result in results:
            symbol = result.get("股票代码")
            review = result_map.get(symbol)
            if review:
                self._merge_review_result(result, review)

        self._write_review_results(review_results)

        return {
            "processed_count": len(review_results),
            "review_results": review_results,
        }

    def backup_csv_if_needed(self, csv_path: Path) -> Optional[Path]:
        """在覆盖CSV前按配置备份已有文件。"""
        if not self.settings.get("write_backup", True):
            return None
        if not csv_path.exists():
            return None
        backup_path = csv_path.with_name(
            f"{csv_path.stem}.before_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}{csv_path.suffix}"
        )
        shutil.copy2(csv_path, backup_path)
        logger.info("已备份二次复核前CSV: %s", backup_path)
        return backup_path

    def _load_settings(self) -> Dict[str, Any]:
        settings = DEFAULT_CONFIG.copy()
        settings["max_workers"] = max(1, int(settings.get("max_workers", 1)))
        settings["timeout_seconds"] = max(1, int(settings.get("timeout_seconds", 60)))
        settings["max_news"] = max(0, int(settings.get("max_news", 6)))
        settings["candidate_actions"] = self._filter_actions(
            settings.get("candidate_actions"),
            VALID_CANDIDATE_ACTIONS,
            DEFAULT_CONFIG["candidate_actions"],
        )
        settings["allowed_final_actions"] = self._filter_actions(
            settings.get("allowed_final_actions"),
            VALID_FINAL_ACTIONS,
            DEFAULT_CONFIG["allowed_final_actions"],
        )
        return settings

    def _create_agent(self) -> BuyConfirmationAgent:
        """基于公共 CLI Agent 门面创建结构化复核器。"""
        return BuyConfirmationAgent(
            agent_type="codex",
            work_dir=str(Path.cwd()),
            on_parse_failure=self.settings.get("on_parse_failure", "hold"),
            candidate_actions=self.settings.get("candidate_actions"),
            allowed_final_actions=self.settings.get("allowed_final_actions"),
        )

    def _filter_actions(
        self,
        actions: Optional[Iterable[str]],
        valid_actions: Iterable[str],
        default_actions: Iterable[str],
    ) -> List[str]:
        if not isinstance(actions, list):
            return list(default_actions)
        valid_set = set(valid_actions)
        filtered = [str(action) for action in actions if str(action) in valid_set]
        return filtered or list(default_actions)

    def _ensure_collectors(self) -> None:
        if self.data_provider is None:
            MultiSourceDataProvider = self._import_collector(
                "src.data.multi_source_data_provider",
                "data.multi_source_data_provider",
                "MultiSourceDataProvider",
            )
            self.data_provider = MultiSourceDataProvider()
        if self.news_fetcher is None:
            RealNewsFetcher = self._import_collector(
                "src.utils.real_news_fetcher",
                "utils.real_news_fetcher",
                "RealNewsFetcher",
            )
            self.news_fetcher = RealNewsFetcher()

    def _import_collector(self, src_module: str, fallback_module: str, class_name: str):
        try:
            module = import_module(src_module)
        except ModuleNotFoundError as exc:
            if exc.name and exc.name != src_module.split(".", 1)[0]:
                raise
            module = import_module(fallback_module)
        return getattr(module, class_name)

    def _find_buy_candidates(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidate_actions = set(self.settings.get("candidate_actions", DEFAULT_CONFIG["candidate_actions"]))
        candidates = [
            result
            for result in results or []
            if result.get("操作建议") in candidate_actions
        ]
        logger.info("买入/持有二次复核候选数量: %s", len(candidates))
        return candidates

    def _review_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        max_workers = min(self.settings["max_workers"], len(candidates))
        reviews = []
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            future_map = {executor.submit(self._review_one, candidate): candidate for candidate in candidates}
            deadlines = {
                future: time.monotonic() + self.settings["timeout_seconds"]
                for future in future_map
            }
            pending = set(future_map)

            while pending:
                now = time.monotonic()
                expired = [future for future in pending if deadlines[future] <= now]
                if expired:
                    for future in expired:
                        pending.remove(future)
                        candidate = future_map[future]
                        future.cancel()
                        reviews.append(
                            self._fallback_for_candidate(
                                candidate,
                                f"二次复核任务超过 {self.settings['timeout_seconds']} 秒未完成",
                                status="timeout",
                            )
                        )
                    continue

                wait_timeout = min(deadlines[future] - now for future in pending)
                done, pending = wait(pending, timeout=wait_timeout, return_when=FIRST_COMPLETED)
                if not done:
                    continue

                for future in done:
                    candidate = future_map[future]
                    try:
                        reviews.append(future.result())
                    except Exception as exc:
                        logger.error("买入/持有二次复核任务失败 %s: %s", candidate.get("股票代码"), exc)
                        reviews.append(
                            self._fallback_for_candidate(
                                candidate,
                                f"二次复核任务失败: {exc}",
                                status="failed",
                            )
                        )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return reviews

    def _review_one(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        context = self._build_context(candidate)
        quality = context.get("data_quality", {})

        if (
            self.settings.get("hold_when_all_external_data_missing", True)
            and not quality.get("fundamental_data_available")
            and not quality.get("sentiment_data_available")
        ):
            return self._fallback_for_context(context, "外部基本面和情绪数据均不可用，按保守策略降级")

        review = self.agent.review(context)
        review["rewrite_action"] = {
            "from": candidate.get("操作建议"),
            "to": review.get("final_action", HOLD_ACTION),
        }
        return review

    def _build_context(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        symbol = candidate.get("股票代码", "")
        stock_name = candidate.get("股票名称", "")
        fundamental_data = self._fetch_fundamental_data(symbol)
        news_data = self._fetch_news(symbol, stock_name)

        return {
            "symbol": symbol,
            "stock_name": stock_name,
            "original_action": candidate.get("操作建议", ""),
            "technical_result": {
                "confidence": candidate.get("置信度") or candidate.get("信心度"),
                "risk_level": candidate.get("风险等级"),
                "current_price": candidate.get("当前价格"),
                "daily_change": candidate.get("当日涨跌"),
                "consecutive_days": candidate.get("连续涨跌天数"),
                "consecutive_change": candidate.get("连续涨跌幅度"),
                "decision_reason": candidate.get("决策理由"),
                "ai_factor_strategy": candidate.get("AI因子_策略"),
                "ai_factor_confidence": candidate.get("AI因子_置信度") or candidate.get("AI因子_信心度"),
            },
            "fundamental_data": fundamental_data,
            "news": news_data,
            "data_quality": {
                "fundamental_data_available": bool(fundamental_data),
                "sentiment_data_available": bool(news_data),
                "news_count": len(news_data),
                "sources": {
                    "fundamental": {
                        "name": "MultiSourceDataProvider.get_fundamental_data",
                        "success": bool(fundamental_data),
                        "records": 1 if fundamental_data else 0,
                        "failure_reason": "" if fundamental_data else "未获取到可用基本面数据",
                    },
                    "sentiment": {
                        "name": "RealNewsFetcher.fetch_stock_news",
                        "success": bool(news_data),
                        "records": len(news_data),
                        "failure_reason": "" if news_data else "未获取到可用新闻/情绪数据",
                    },
                },
            },
        }

    def _fetch_fundamental_data(self, symbol: str) -> Dict[str, Any]:
        try:
            data = self.data_provider.get_fundamental_data(symbol)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            logger.warning("获取基本面数据失败 %s: %s", symbol, exc)
        return {}

    def _fetch_news(self, symbol: str, stock_name: str) -> List[Dict[str, Any]]:
        try:
            news = self.news_fetcher.fetch_stock_news(symbol, stock_name)
            if not isinstance(news, list):
                return []
            return [self._summarize_news_item(item) for item in news[: self.settings["max_news"]]]
        except Exception as exc:
            logger.warning("获取新闻情绪数据失败 %s: %s", symbol, exc)
            return []

    def _summarize_news_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": item.get("title", ""),
            "content": str(item.get("content", ""))[:300],
            "source": item.get("source") or item.get("aggregated_source", ""),
            "time": item.get("time", ""),
            "url": item.get("url", ""),
        }

    def _merge_review_result(self, result: Dict[str, Any], review: Dict[str, Any]) -> None:
        if review.get("agent_parse_status") != "success":
            logger.info("买入/持有二次复核未成功，保留原始建议 %s", result.get("股票代码"))
            return

        original_action = result.get("操作建议", "")
        final_action = review.get("final_action", HOLD_ACTION)
        if original_action not in set(self.settings.get("candidate_actions", [])):
            return
        if final_action not in set(self.settings.get("allowed_final_actions", [])):
            final_action = HOLD_ACTION

        result["原操作建议"] = original_action
        result["操作建议"] = final_action
        result["Agent复核建议"] = final_action
        confidence_display = f"{float(review.get('confidence', 0.0)):.2%}"
        result["Agent复核置信度"] = confidence_display
        result["Agent复核信心度"] = confidence_display
        result["Agent基本面观点"] = review.get("fundamental_view", "unknown")
        result["Agent情绪面观点"] = review.get("sentiment_view", "unknown")
        result["Agent风险提示"] = "；".join(str(flag) for flag in review.get("risk_flags", []))
        result["Agent复核理由"] = review.get("reason", "")
        result["Agent数据质量"] = json.dumps(review.get("data_quality", {}), ensure_ascii=False)
        result["Agent解析状态"] = review.get("agent_parse_status", "unknown")

        logger.info("买入/持有二次复核改写 %s: %s -> %s", result.get("股票代码"), original_action, final_action)

    def _write_review_results(self, reviews: List[Dict[str, Any]]) -> None:
        if not self.output_dir:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            path = self.output_dir / "agent_review_results.json"
            with open(path, "w", encoding="utf-8") as file:
                json.dump(reviews, file, ensure_ascii=False, indent=2, default=str)
            logger.info("买入/持有二次复核结果已保存: %s", path)
        except Exception as exc:
            logger.error("保存买入/持有二次复核结果失败: %s", exc)
            raise

    def _fallback_for_candidate(
        self,
        candidate: Dict[str, Any],
        reason: str,
        status: str = "data_unavailable",
        data_quality: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = {
            "symbol": candidate.get("股票代码", ""),
            "stock_name": candidate.get("股票名称", ""),
            "original_action": candidate.get("操作建议", ""),
            "data_quality": data_quality or {},
        }
        return self._fallback_for_context(context, reason, status=status)

    def _collector_init_failure_quality(self, reason: str) -> Dict[str, Any]:
        return {
            "fundamental_data_available": False,
            "sentiment_data_available": False,
            "news_count": 0,
            "sources": {
                "fundamental": {
                    "name": "MultiSourceDataProvider.get_fundamental_data",
                    "success": False,
                    "records": 0,
                    "failure_reason": reason,
                },
                "sentiment": {
                    "name": "RealNewsFetcher.fetch_stock_news",
                    "success": False,
                    "records": 0,
                    "failure_reason": reason,
                },
            },
        }

    def _fallback_for_context(
        self,
        context: Dict[str, Any],
        reason: str,
        status: str = "data_unavailable",
    ) -> Dict[str, Any]:
        return {
            "symbol": context.get("symbol", ""),
            "stock_name": context.get("stock_name", ""),
            "original_action": context.get("original_action", ""),
            "final_action": HOLD_ACTION,
            "confidence": 0.0,
            "fundamental_view": "unknown",
            "sentiment_view": "unknown",
            "risk_flags": ["二次复核数据不足"],
            "reason": reason,
            "evidence": [],
            "data_quality": context.get("data_quality", {}),
            "agent_parse_status": status,
            "raw_output": "",
            "rewrite_action": {
                "from": context.get("original_action", ""),
                "to": HOLD_ACTION,
            },
        }
