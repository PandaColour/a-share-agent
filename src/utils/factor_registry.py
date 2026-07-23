# -*- coding: utf-8 -*-
"""
生产因子注册表读写工具
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable


REGISTRY_KEYS = ("active_factors", "candidate_factors", "disabled_factors")


class FactorRegistryManager:
    """管理候选、生产、禁用因子的JSON配置"""

    def __init__(self, registry_path="config/factor_registry.json"):
        self.registry_path = Path(registry_path)

    def load(self) -> Dict:
        """加载注册表，不存在时创建默认结构"""
        if not self.registry_path.exists():
            registry = self._default_registry()
            self.save(registry)
            return registry

        with self.registry_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return self._normalize(data)

    def save(self, registry: Dict) -> Dict:
        """保存注册表并返回规范化后的结构"""
        normalized = self._normalize(registry)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.registry_path.open("w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return normalized

    def move_factor(self, factor_name: str, target_key: str) -> Dict:
        """将因子移动到指定列表，并从其它列表移除"""
        if target_key not in REGISTRY_KEYS:
            raise ValueError(f"未知因子列表: {target_key}")

        factor_name = factor_name.strip()
        if not factor_name:
            raise ValueError("因子名称不能为空")

        registry = self.load()
        for key in REGISTRY_KEYS:
            registry[key] = [name for name in registry[key] if name != factor_name]

        registry[target_key].append(factor_name)
        return self.save(registry)

    def _default_registry(self) -> Dict:
        return {
            "active_factors": [],
            "candidate_factors": [],
            "disabled_factors": [],
            "version": datetime.now().strftime("%Y-%m-%d")
        }

    def _normalize(self, registry: Dict) -> Dict:
        normalized = {
            "version": registry.get("version") or datetime.now().strftime("%Y-%m-%d")
        }

        seen = set()
        for key in REGISTRY_KEYS:
            values = registry.get(key, [])
            normalized[key] = self._unique_strings(values, seen)

        return {
            "active_factors": normalized["active_factors"],
            "candidate_factors": normalized["candidate_factors"],
            "disabled_factors": normalized["disabled_factors"],
            "version": normalized["version"]
        }

    def _unique_strings(self, values: Iterable, global_seen: set) -> list:
        unique = []
        for value in values:
            if not isinstance(value, str):
                continue
            name = value.strip()
            if not name or name in global_seen:
                continue
            unique.append(name)
            global_seen.add(name)
        return unique
