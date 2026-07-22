# -*- coding: utf-8 -*-
"""
买入/持有信号二次复核 Agent。

复核器默认复用 ``src.agents.Agent`` 这个 Claude/Codex/Cursor CLI 门面。
本类只负责交易复核上下文封装、JSON 提取、字段校验和保守降级，不直接使用
AIModelInterface 绕过通用 Agent。
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)

BUY_ACTION = "买入"
HOLD_ACTION = "持有"
SELL_ACTION = "卖出"
VALID_CANDIDATE_ACTIONS = {BUY_ACTION, HOLD_ACTION}
VALID_FINAL_ACTIONS = {BUY_ACTION, HOLD_ACTION, SELL_ACTION}
VALID_PARSE_FAILURE_POLICIES = {"hold", "keep_original"}


class BuyConfirmationAgent:
    """复用 ``src.agents.Agent`` 的买入/持有结构化 CLI 复核包装器。

    该类负责 JSON 输出约束、JSON 提取、字段校验和失败降级，避免绕过
    通用 Agent 门面回退到独立模型调用路径。
    """

    def __init__(
        self,
        agent=None,
        agent_factory: Optional[Callable[..., Any]] = None,
        agent_type: str = "codex",
        work_dir: Optional[str] = None,
        on_parse_failure: str = "hold",
        candidate_actions: Optional[Iterable[str]] = None,
        allowed_final_actions: Optional[Iterable[str]] = None,
        prompt_file: Optional[str] = None,
    ):
        self.agent = agent
        self.agent_factory = agent_factory
        self.agent_type = agent_type or "codex"
        self.work_dir = work_dir or os.getcwd()
        self.on_parse_failure = (
            on_parse_failure
            if on_parse_failure in VALID_PARSE_FAILURE_POLICIES
            else "hold"
        )
        self.candidate_actions = self._normalize_actions(
            candidate_actions,
            VALID_CANDIDATE_ACTIONS,
            VALID_CANDIDATE_ACTIONS,
        )
        self.allowed_final_actions = self._normalize_actions(
            allowed_final_actions,
            VALID_FINAL_ACTIONS,
            VALID_FINAL_ACTIONS,
        )
        self.prompt_file = prompt_file or self._default_prompt_file()
        if HOLD_ACTION not in self.allowed_final_actions:
            self.allowed_final_actions.add(HOLD_ACTION)

    def review(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行单只股票复核并返回已校验的结构化结果。"""
        symbol = context.get("symbol", "")
        stock_name = context.get("stock_name", "")
        original_action = context.get("original_action", "")

        if original_action not in self.candidate_actions:
            return self._fallback_result(
                context,
                "skipped",
                f"原始建议 {original_action} 不在二次复核候选范围内",
                raw_output="",
            )

        prompt = self._build_prompt(context)
        try:
            raw_output = self._get_agent().send_message(prompt)
        except Exception as exc:
            logger.error("买入/持有二次复核 Agent 调用失败 %s: %s", symbol, exc)
            return self._fallback_result(
                context,
                "agent_error",
                f"复核 Agent 调用失败: {exc}",
                raw_output="",
            )

        parsed = self.parse_and_validate(raw_output, context)
        logger.info(
            "买入/持有二次复核完成 %s(%s): %s -> %s, status=%s",
            stock_name,
            symbol,
            original_action,
            parsed.get("final_action"),
            parsed.get("agent_parse_status"),
        )
        return parsed

    def parse_and_validate(self, raw_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """解析并校验 Agent 输出。"""
        try:
            payload = self._extract_json(raw_output)
            if isinstance(payload, list):
                if not payload:
                    raise ValueError("JSON数组为空")
                payload = payload[0]
            if not isinstance(payload, dict):
                raise ValueError("Agent输出不是JSON对象")

            result = self._normalize_result(payload, context, raw_output)
            self._validate_result(result)
            result["agent_parse_status"] = "success"
            return result
        except Exception as exc:
            logger.warning("买入/持有二次复核输出解析失败 %s: %s", context.get("symbol", ""), exc)
            return self._fallback_result(
                context,
                "failed",
                f"Agent输出解析或校验失败: {exc}",
                raw_output=raw_output,
            )

    def _get_agent(self):
        if self.agent is not None:
            return self.agent
        if self.agent_factory is None:
            from src.agents import Agent

            self.agent_factory = Agent

        self.agent = self.agent_factory(
            name="买入持有二次复核Agent",
            system_prompt_file=None,
            work_dir=self.work_dir,
            agent_type=self.agent_type,
        )
        return self.agent

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        schema = {
            "symbol": context.get("symbol", ""),
            "stock_name": context.get("stock_name", ""),
            "original_action": context.get("original_action", ""),
            "final_action": "买入/持有/卖出",
            "confidence": 0.0,
            "fundamental_view": "positive/neutral/negative/unknown",
            "sentiment_view": "positive/neutral/negative/unknown",
            "risk_flags": ["风险提示"],
            "reason": "结构化复核原因",
            "evidence": [{"type": "news", "source": "source", "summary": "摘要", "url": ""}],
            "data_quality": context.get("data_quality", {}),
        }
        return self._load_prompt_template().format(
            original_action=context.get("original_action", ""),
            allowed_actions=sorted(self.allowed_final_actions),
            schema_json=json.dumps(schema, ensure_ascii=False, indent=2),
            context_json=json.dumps(context, ensure_ascii=False, indent=2, default=str),
        )

    def _default_prompt_file(self) -> str:
        return str(Path(__file__).resolve().parents[2] / "config" / "buy_confirmation_prompt.md")

    def _load_prompt_template(self) -> str:
        return Path(self.prompt_file).read_text(encoding="utf-8")

    def _extract_json(self, raw_output: str) -> Any:
        if not raw_output or not str(raw_output).strip():
            raise ValueError("Agent输出为空")

        text = str(raw_output).strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            object_match = re.search(r"(\{.*\})", text, re.DOTALL)
            array_match = re.search(r"(\[.*\])", text, re.DOTALL)
            match = object_match or array_match
            if not match:
                raise
            return json.loads(match.group(1))

    def _normalize_result(
        self,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        raw_output: str,
    ) -> Dict[str, Any]:
        data_quality = payload.get("data_quality") or {}
        evidence = payload.get("evidence") or []
        risk_flags = payload.get("risk_flags") or []

        return {
            "symbol": str(payload.get("symbol") or context.get("symbol") or ""),
            "stock_name": str(payload.get("stock_name") or context.get("stock_name") or ""),
            "original_action": str(payload.get("original_action") or context.get("original_action") or ""),
            "final_action": str(payload.get("final_action") or ""),
            "confidence": float(payload.get("confidence")),
            "fundamental_view": str(payload.get("fundamental_view") or "unknown"),
            "sentiment_view": str(payload.get("sentiment_view") or "unknown"),
            "risk_flags": risk_flags if isinstance(risk_flags, list) else [str(risk_flags)],
            "reason": str(payload.get("reason") or ""),
            "evidence": evidence if isinstance(evidence, list) else [],
            "data_quality": data_quality if isinstance(data_quality, dict) else {},
            "raw_output": raw_output,
        }

    def _validate_result(self, result: Dict[str, Any]) -> None:
        if result["original_action"] not in self.candidate_actions:
            raise ValueError("original_action不在候选动作范围内")
        if result["final_action"] not in self.allowed_final_actions:
            raise ValueError("final_action非法")
        if not 0 <= result["confidence"] <= 1:
            raise ValueError("confidence超出0到1范围")
        if not result["reason"]:
            raise ValueError("reason不能为空")

    def _fallback_result(
        self,
        context: Dict[str, Any],
        status: str,
        reason: str,
        raw_output: str,
    ) -> Dict[str, Any]:
        original_action = str(context.get("original_action") or "")
        final_action = HOLD_ACTION
        if (
            self.on_parse_failure == "keep_original"
            and status == "failed"
            and original_action in self.allowed_final_actions
        ):
            final_action = original_action

        return {
            "symbol": str(context.get("symbol") or ""),
            "stock_name": str(context.get("stock_name") or ""),
            "original_action": original_action,
            "final_action": final_action,
            "confidence": 0.0,
            "fundamental_view": "unknown",
            "sentiment_view": "unknown",
            "risk_flags": ["二次复核未获得有效结构化结论"],
            "reason": reason,
            "evidence": [],
            "data_quality": context.get("data_quality", {}),
            "agent_parse_status": status,
            "raw_output": raw_output,
        }

    def _normalize_actions(
        self,
        actions: Optional[Iterable[str]],
        valid_actions: Set[str],
        default_actions: Set[str],
    ) -> Set[str]:
        if not actions:
            return set(default_actions)
        normalized = {str(action) for action in actions if str(action) in valid_actions}
        return normalized or set(default_actions)
