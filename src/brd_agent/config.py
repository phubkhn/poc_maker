"""Configuration values for the BRD agent scaffold."""

import os
from dataclasses import dataclass
from pathlib import Path

VALID_AGENT_MODES = ("deterministic", "llm", "hybrid")

DEFAULT_ARTIFACT_DIR = Path("artifacts")
DEFAULT_BRD_NORMALIZED_NAME = "brd_normalized.json"
DEFAULT_CONTEXT_NAME = "context.md"
DEFAULT_GAPS_NAME = "brd_gaps.md"
DEFAULT_TASK_NAME = "task.md"
DEFAULT_ACCEPTANCE_NAME = "acceptance_criteria.md"
DEFAULT_ARCHITECTURE_NAME = "architecture.md"
DEFAULT_DEV_PLAN_NAME = "dev_plan.md"
DEFAULT_BRD_PROMPT_PATH = Path("prompts/brd_extraction_prompt.md")
DEFAULT_BA_PROMPT_PATH = Path("prompts/ba_task_prompt.md")
DEFAULT_BA_REVIEW_PROMPT_PATH = Path("prompts/ba_review_prompt.md")
DEFAULT_SA_ARCH_PROMPT_PATH = Path("prompts/sa_architecture_prompt.md")
DEFAULT_SA_PLAN_PROMPT_PATH = Path("prompts/sa_dev_plan_prompt.md")
DEFAULT_SA_ARCH_REVIEW_PROMPT_PATH = Path("prompts/sa_architecture_review_prompt.md")
DEFAULT_SA_PLAN_REVIEW_PROMPT_PATH = Path("prompts/sa_dev_plan_review_prompt.md")
DEFAULT_DEV_REVIEW_PROMPT_PATH = Path("prompts/dev_review_prompt.md")


@dataclass
class LLMSettings(object):
    model_name: str
    api_key: str
    base_url: str
    temperature: float
    prompt_path: Path


@dataclass
class SASettings(object):
    model_name: str
    api_key: str
    base_url: str
    temperature: float
    architecture_prompt_path: Path
    dev_plan_prompt_path: Path


def _load_mode(env_key, default_value="hybrid"):
    value = os.getenv(env_key, default_value).strip().lower()
    if value not in VALID_AGENT_MODES:
        raise ValueError(
            "Invalid {0}: {1}. Expected one of: {2}".format(
                env_key,
                value,
                ", ".join(VALID_AGENT_MODES),
            )
        )
    return value


def load_llm_settings():
    """Load LLM settings from environment variables."""
    model_name = os.getenv("BRD_LLM_MODEL", "gpt-4o-mini")
    api_key = os.getenv("BRD_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("BRD_LLM_BASE_URL", "")
    prompt_path = Path(
        os.getenv("BRD_EXTRACTION_PROMPT_PATH", str(DEFAULT_BRD_PROMPT_PATH))
    )

    temperature_raw = os.getenv("BRD_LLM_TEMPERATURE", "0")
    try:
        temperature = float(temperature_raw)
    except ValueError:
        raise ValueError(
            "Invalid BRD_LLM_TEMPERATURE value: {0}".format(temperature_raw)
        )

    return LLMSettings(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        prompt_path=prompt_path,
    )


def load_brd_analyzer_mode():
    return _load_mode("BRD_ANALYZER_MODE", "hybrid")


def load_ba_llm_settings():
    """Load BA generation settings from environment variables."""
    model_name = os.getenv("BA_LLM_MODEL", os.getenv("BRD_LLM_MODEL", "gpt-4o-mini"))
    api_key = os.getenv("BA_LLM_API_KEY") or os.getenv("BRD_LLM_API_KEY")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    base_url = os.getenv("BA_LLM_BASE_URL", os.getenv("BRD_LLM_BASE_URL", ""))
    prompt_path = Path(
        os.getenv("BA_TASK_PROMPT_PATH", str(DEFAULT_BA_PROMPT_PATH))
    )

    temperature_raw = os.getenv("BA_LLM_TEMPERATURE", "0.2")
    try:
        temperature = float(temperature_raw)
    except ValueError:
        raise ValueError(
            "Invalid BA_LLM_TEMPERATURE value: {0}".format(temperature_raw)
        )

    return LLMSettings(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        prompt_path=prompt_path,
    )


def load_ba_agent_mode():
    return _load_mode("BA_AGENT_MODE", "hybrid")


def load_sa_llm_settings():
    """Load SA generation settings from environment variables."""
    model_name = os.getenv("SA_LLM_MODEL", os.getenv("BA_LLM_MODEL", "gpt-4o-mini"))
    api_key = os.getenv("SA_LLM_API_KEY") or os.getenv("BA_LLM_API_KEY")
    if not api_key:
        api_key = os.getenv("BRD_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")

    base_url = os.getenv("SA_LLM_BASE_URL", os.getenv("BA_LLM_BASE_URL", ""))
    arch_prompt_path = Path(
        os.getenv("SA_ARCH_PROMPT_PATH", str(DEFAULT_SA_ARCH_PROMPT_PATH))
    )
    dev_plan_prompt_path = Path(
        os.getenv("SA_DEV_PLAN_PROMPT_PATH", str(DEFAULT_SA_PLAN_PROMPT_PATH))
    )

    temperature_raw = os.getenv("SA_LLM_TEMPERATURE", "0.2")
    try:
        temperature = float(temperature_raw)
    except ValueError:
        raise ValueError(
            "Invalid SA_LLM_TEMPERATURE value: {0}".format(temperature_raw)
        )

    return SASettings(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        architecture_prompt_path=arch_prompt_path,
        dev_plan_prompt_path=dev_plan_prompt_path,
    )


def load_ba_review_prompt_path():
    return Path(
        os.getenv("BA_REVIEW_PROMPT_PATH", str(DEFAULT_BA_REVIEW_PROMPT_PATH))
    )


def load_ba_review_iterations():
    raw = os.getenv("BA_REVIEW_ITERATIONS", "1")
    try:
        value = int(raw)
    except ValueError:
        raise ValueError("Invalid BA_REVIEW_ITERATIONS value: {0}".format(raw))
    return max(0, value)


def load_sa_review_prompt_paths():
    return {
        "architecture": Path(
            os.getenv(
                "SA_ARCH_REVIEW_PROMPT_PATH",
                str(DEFAULT_SA_ARCH_REVIEW_PROMPT_PATH),
            )
        ),
        "dev_plan": Path(
            os.getenv(
                "SA_DEV_PLAN_REVIEW_PROMPT_PATH",
                str(DEFAULT_SA_PLAN_REVIEW_PROMPT_PATH),
            )
        ),
    }


def load_sa_review_iterations():
    raw = os.getenv("SA_REVIEW_ITERATIONS", "1")
    try:
        value = int(raw)
    except ValueError:
        raise ValueError("Invalid SA_REVIEW_ITERATIONS value: {0}".format(raw))
    return max(0, value)


def load_dev_review_prompt_path():
    return Path(
        os.getenv("DEV_REVIEW_PROMPT_PATH", str(DEFAULT_DEV_REVIEW_PROMPT_PATH))
    )


def load_sa_agent_mode():
    return _load_mode("SA_AGENT_MODE", "hybrid")
