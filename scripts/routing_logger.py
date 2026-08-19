#!/usr/bin/env python3
"""
Custom LiteLLM callback to log routing decisions.

Logs which model tier was selected for each request to enable analysis and debugging.
Enable by adding to config.yaml callbacks list:
  callbacks:
    - scripts.routing_logger.proxy_handler_instance
"""

from litellm.integrations.custom_logger import CustomLogger
import logging
import json
from datetime import datetime
from typing import Any, Optional, Dict

logger = None

def _init_logger():
    global logger
    if logger is not None:
        return

    logger = logging.getLogger("routing_decision_logger")
    logger.setLevel(logging.INFO)

    # Configure file handler
    file_handler = logging.FileHandler("/tmp/litellm_routing.log")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - ROUTING - %(levelname)s - %(message)s'))

    # Configure stream handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s - ROUTING - %(levelname)s - %(message)s'))

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


class RoutingDecisionLogger(CustomLogger):
    """
    Logs routing decisions for analysis and debugging.

    Tracks:
    - Which tier (SIMPLE/COMPLEX/REASONING) was selected
    - Prompt preview and length
    - Model latency
    - Token usage
    - Errors and retries
    """

    def __init__(self):
        super().__init__()
        _init_logger()

    def log_pre_api_call(self, model: str = "unknown", messages: Optional[list] = None, **kwargs) -> None:
        """Log details before making the API call."""
        try:
            if messages is None:
                messages = kwargs.get("messages", [])

            # Extract first user message as prompt preview
            prompt_preview = ""
            prompt_length = 0
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    prompt_length = len(content)
                    prompt_preview = content[:100] + "..." if len(content) > 100 else content
                    break

            # Log pre-call info
            routing_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "requested_model": model,
                "prompt_preview": prompt_preview,
                "prompt_length": prompt_length,
            }

            logger.info(f"PRE_CALL: {json.dumps(routing_data)}")
            # Flush all handlers to ensure immediate write to file
            for handler in logger.handlers:
                handler.flush()

        except Exception as e:
            logger.error(f"Error logging pre-call: {e}")
            for handler in logger.handlers:
                handler.flush()

    def log_success_event(self, model: str = "unknown", messages: Optional[list] = None, response_obj: Any = None, start_time: Optional[float] = None, end_time: Optional[float] = None, **kwargs) -> None:
        """Log successful completion with routing decision."""
        try:
            if messages is None:
                messages = kwargs.get("messages", [])

            # Determine which tier was actually used
            actual_model = response_obj.model if hasattr(response_obj, "model") else "unknown"

            if "haiku" in actual_model.lower():
                tier = "SIMPLE"
            elif "sonnet" in actual_model.lower():
                tier = "COMPLEX"
            elif "opus" in actual_model.lower():
                tier = "REASONING"
            else:
                tier = "UNKNOWN"

            # Extract prompt preview
            prompt_preview = ""
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    prompt_preview = content[:80] + "..." if len(content) > 80 else content
                    break

            # Calculate latency
            latency_ms = 0
            if start_time and end_time:
                diff = end_time - start_time
                if hasattr(diff, 'total_seconds'):
                    latency_ms = diff.total_seconds() * 1000
                else:
                    latency_ms = diff * 1000

            # Get token usage
            usage = response_obj.usage if hasattr(response_obj, "usage") else {}
            total_tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else getattr(usage, "total_tokens", 0)

            routing_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "requested_model": model,
                "actual_model": actual_model,
                "tier": tier,
                "prompt_preview": prompt_preview,
                "latency_ms": round(latency_ms, 2) if isinstance(latency_ms, (int, float)) else latency_ms,
                "total_tokens": total_tokens,
                "status": "success",
            }

            logger.info(f"SUCCESS: {json.dumps(routing_data)}")
            # Flush all handlers to ensure immediate write to file
            for handler in logger.handlers:
                handler.flush()

        except Exception as e:
            logger.error(f"Error logging success event: {e}")
            for handler in logger.handlers:
                handler.flush()

    def log_failure_event(self, model: str = "unknown", messages: Optional[list] = None, response_obj: Any = None, start_time: Optional[float] = None, end_time: Optional[float] = None, **kwargs) -> None:
        """Log failed requests."""
        try:
            if messages is None:
                messages = kwargs.get("messages", [])

            error_msg = str(response_obj) if response_obj else "unknown_error"

            # Extract prompt preview
            prompt_preview = ""
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    prompt_preview = content[:80] + "..." if len(content) > 80 else content
                    break

            # Calculate latency
            latency_ms = 0
            if start_time and end_time:
                diff = end_time - start_time
                if hasattr(diff, 'total_seconds'):
                    latency_ms = diff.total_seconds() * 1000
                else:
                    latency_ms = diff * 1000

            routing_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "requested_model": model,
                "prompt_preview": prompt_preview,
                "error": error_msg[:200],
                "latency_ms": round(latency_ms, 2) if isinstance(latency_ms, (int, float)) else latency_ms,
                "status": "failure",
            }

            logger.warning(f"FAILURE: {json.dumps(routing_data)}")
            # Flush all handlers to ensure immediate write to file
            for handler in logger.handlers:
                handler.flush()

        except Exception as e:
            logger.error(f"Error logging failure event: {e}")
            for handler in logger.handlers:
                handler.flush()


# Create instance for LiteLLM to use
proxy_handler_instance = RoutingDecisionLogger()
