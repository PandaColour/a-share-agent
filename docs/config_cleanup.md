# 配置文件清理说明

## 日期: 2025-10-20

## 清理内容

### 删除无用配置: `analyst_assignments.debate`

**位置**: `config/unified_config.json` -> `ai_models.analyst_assignments.debate`

**原因**:
- 系统已改用独立的看涨/看跌研究员模型配置
- `debate` 配置在代码中没有任何引用
- 保留会造成配置混乱

### 实际使用的配置

系统使用以下分析师模型分配:

```json
{
  "analyst_assignments": {
    "fundamental": "deepseek-v3.1",        // 基本面分析师
    "technical": "deepseek-v3.2",          // 技术面分析师
    "sentiment": "deepseek-v3.1",          // 情感面分析师
    "bull_researcher": "deepseek-v3.1",    // 看涨研究员 (辩论系统)
    "bear_researcher": "deepseek-v3.2"     // 看跌研究员 (辩论系统)
  }
}
```

### 代码验证

在以下文件中验证了配置的实际使用方式:

1. **`src/agents/multi_round_bull_researcher.py`** (第36, 50行)
   ```python
   self.agent_type = "bull_researcher"
   model_name = analyst_assignments.get(self.agent_type, ...)
   ```

2. **`src/agents/multi_round_bear_researcher.py`** (类似逻辑)
   ```python
   self.agent_type = "bear_researcher"
   model_name = analyst_assignments.get(self.agent_type, ...)
   ```

通过grep搜索确认:
- `analyst_assignments.*debate` - 没有匹配结果
- `"debate"` 在配置中只用于 `debate_settings` 和 `debate_prompts`,不用于模型分配

### 修改前后对比

**修改前**:
```json
"analyst_assignments": {
  "fundamental": "deepseek-v3.1",
  "technical": "deepseek-v3.2",
  "sentiment": "deepseek-v3.1",
  "debate": "deepseek-r1-0528",           // ← 无用配置
  "bull_researcher": "deepseek-v3.1",
  "bear_researcher": "deepseek-v3.2"
}
```

**修改后**:
```json
"analyst_assignments": {
  "fundamental": "deepseek-v3.1",
  "technical": "deepseek-v3.2",
  "sentiment": "deepseek-v3.1",
  "bull_researcher": "deepseek-v3.1",
  "bear_researcher": "deepseek-v3.2"
}
```

## 影响评估

### 无影响

- ✅ 代码中没有任何地方使用 `analyst_assignments.debate`
- ✅ 辩论系统使用 `bull_researcher` 和 `bear_researcher` 配置
- ✅ 其他分析师配置保持不变
- ✅ 向后兼容,不影响现有功能

### 改进

- ✅ 配置文件更清晰
- ✅ 减少配置冗余
- ✅ 避免用户混淆
- ✅ 降低维护成本

## 相关配置说明

### 辩论系统配置

辩论系统的配置分为两部分:

1. **辩论行为配置**: `system_settings.debate_settings`
   ```json
   {
     "enable_debate": true,
     "enable_multi_round_debate": true,
     "debate_rounds": 2,
     "force_opposing_views": true,
     "min_confidence_threshold": 0.6
   }
   ```

2. **辩论Prompt配置**: `system_settings.debate_prompts`
   ```json
   {
     "bull_researcher": {
       "system_prompt": "...",
       "debate_prompt": "..."
     },
     "bear_researcher": {
       "system_prompt": "...",
       "debate_prompt": "..."
     }
   }
   ```

3. **模型分配**: `ai_models.analyst_assignments`
   ```json
   {
     "bull_researcher": "deepseek-v3.1",
     "bear_researcher": "deepseek-v3.2"
   }
   ```

## 建议

如果将来需要为辩论系统配置专用模型,建议:

1. **不要**使用 `analyst_assignments.debate` (已证实不会被使用)
2. **应该**直接修改 `bull_researcher` 和 `bear_researcher` 的模型分配
3. **或者**在代码中添加对 `debate` 配置的支持(需要修改代码)

## 验证

可以通过以下命令验证配置的使用情况:

```bash
# 搜索代码中对 debate 配置的引用
grep -r "analyst_assignments.*debate" src/
grep -r '\["debate"\]' src/
grep -r "\.get\(.*debate" src/

# 搜索实际使用的配置
grep -r "bull_researcher" src/
grep -r "bear_researcher" src/
```

## 总结

`analyst_assignments.debate` 是一个遗留配置,在当前代码中没有任何作用。删除后:
- 配置更简洁
- 逻辑更清晰
- 不影响任何功能
- 推荐保持删除状态
