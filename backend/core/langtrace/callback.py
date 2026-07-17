"""
core/langtrace/callback.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
LangChain Callback Handler for real-time cost and token interception.
"""

import os
import json
from datetime import datetime, timezone
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from core.engine.memory import RedisClient
from .pricing import get_cost, count_tokens

_redis_instance = RedisClient()
_redis = _redis_instance.get_client()


class LangTraceCallbackHandler(BaseCallbackHandler):
    """
    LangChain Callback Handler that records LLM input/output tokens and cost in real-time,
    storing granular metric breakdowns to Redis.
    """

    def __init__(
        self,
        session_id: str,
        agent_name: str,
        purpose: str,
        system_prompt: str = "",
        skill: str = "",
        conversation_history: str = "",
        tool_report: str = "",
        execution_report: dict = None,
        routing_context: str = "",
    ):
        self.session_id = session_id
        self.agent_name = agent_name
        self.purpose = purpose
        self.system_prompt = system_prompt
        self.skill = skill
        self.conversation_history = conversation_history
        self.tool_report = tool_report
        # Safely serialize Pydantic objects or dictionaries to prevent serialization errors
        if execution_report:
            try:
                serializable_report = {}
                for k, v in execution_report.items():
                    if hasattr(v, "dict"):
                        serializable_report[k] = v.dict()
                    elif hasattr(v, "model_dump"):
                        serializable_report[k] = v.model_dump()
                    else:
                        serializable_report[k] = v
                self.execution_report_str = json.dumps(serializable_report)
            except Exception:
                self.execution_report_str = str(execution_report)
        else:
            self.execution_report_str = ""
        self.routing_context = routing_context

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        try:
            llm_output = response.llm_output or {}
            
            # Resolve model name safely
            run_props = getattr(response, "run_properties", {}) or {}
            model_name = (
                run_props.get("model_name")
                or llm_output.get("model_name")
                or os.getenv("MODEL_EXEC_MOONSHOT", "kimi-k2.5")
            )

            # Resolve token usage
            token_usage = {}
            if "token_usage" in llm_output:
                token_usage = llm_output["token_usage"]
            elif response.generations and response.generations[0]:
                gen_msg = response.generations[0][0].message
                if hasattr(gen_msg, "usage_metadata") and gen_msg.usage_metadata:
                    token_usage = gen_msg.usage_metadata

            input_tokens = token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0
            output_tokens = token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0

            # Local fallback
            if input_tokens == 0:
                input_tokens = count_tokens(self.system_prompt + self.routing_context, model_name)
            if output_tokens == 0 and response.generations and response.generations[0]:
                out_content = "".join(g.text for g in response.generations[0])
                output_tokens = count_tokens(out_content, model_name)

            # GRANULAR TOKEN BREAKDOWN
            skill_t = count_tokens(self.skill, model_name)
            history_t = count_tokens(self.conversation_history, model_name)
            tool_report_t = count_tokens(self.tool_report, model_name)
            exec_report_t = count_tokens(self.execution_report_str, model_name)
            routing_t = count_tokens(self.routing_context, model_name)

            sys_prompt_t = count_tokens(self.system_prompt, model_name)
            skeleton_t = max(0, sys_prompt_t - (skill_t + history_t + tool_report_t + exec_report_t))

            # Calculated Cost
            cost = get_cost(model_name, input_tokens, output_tokens)

            # Compile trace entry
            record = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "agent_name": self.agent_name,
                "purpose": self.purpose,
                "model_name": model_name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "breakdown": {
                    "skeleton_tokens": skeleton_t,
                    "skill_tokens": skill_t,
                    "conversation_memory_tokens": history_t,
                    "tool_ledger_tokens": tool_report_t,
                    "execution_report_tokens": exec_report_t,
                    "routing_context_tokens": routing_t,
                }
            }

            # Save to Redis
            key = f"langtrace:{self.session_id}:calls"
            _redis.rpush(key, json.dumps(record))
            _redis.expire(key, 604800)  # 7-day TTL

        except Exception as e:
            print(f"⚠️ [LangTrace] Callback failed: {e}")
