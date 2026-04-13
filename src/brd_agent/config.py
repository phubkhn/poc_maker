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
DEFAULT_GENERATED_CODE_NAME = "generated_code.md"
DEFAULT_QA_TEST_PLAN_NAME = "qa_test_plan.md"
DEFAULT_QA_TEST_CASES_NAME = "qa_test_cases.md"
DEFAULT_CODE_STANDARDS_NAME = "code_standards.md"
DEFAULT_REVIEW_STANDARDS_NAME = "review_standards.md"

DEFAULT_BRD_PROMPT_PATH = Path("prompts/brd_extraction_prompt.md")
DEFAULT_BA_PROMPT_PATH = Path("prompts/ba_task_prompt.md")
DEFAULT_BA_REVIEW_PROMPT_PATH = Path("prompts/ba_review_prompt.md")
DEFAULT_SA_ARCH_PROMPT_PATH = Path("prompts/sa_architecture_prompt.md")
DEFAULT_SA_PLAN_PROMPT_PATH = Path("prompts/sa_dev_plan_prompt.md")
DEFAULT_SA_ARCH_REVIEW_PROMPT_PATH = Path("prompts/sa_architecture_review_prompt.md")
DEFAULT_SA_PLAN_REVIEW_PROMPT_PATH = Path("prompts/sa_dev_plan_review_prompt.md")
DEFAULT_DEV_CODE_PROMPT_PATH = Path("prompts/dev_code_prompt.md")
DEFAULT_DEV_REVIEW_PROMPT_PATH = Path("prompts/dev_review_prompt.md")
DEFAULT_QA_PLAN_PROMPT_PATH = Path("prompts/qa_test_plan_prompt.md")
DEFAULT_QA_REVIEW_PROMPT_PATH = Path("prompts/qa_review_prompt.md")


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


def _read_temperature(env_key, default_value):
    raw = os.getenv(env_key, default_value)
    try:
        return float(raw)
    except ValueError:
        raise ValueError("Invalid {0} value: {1}".format(env_key, raw))


def _read_iterations(env_key, default_value="1"):
    raw = os.getenv(env_key, default_value)
    try:
        value = int(raw)
    except ValueError:
        raise ValueError("Invalid {0} value: {1}".format(env_key, raw))
    return max(0, value)


def _resolve_api_key(primary_env, fallback_envs):
    api_key = os.getenv(primary_env)
    if api_key:
        return api_key
    for key in fallback_envs:
        value = os.getenv(key)
        if value:
            return value
    return None


def _normalize_model_name(model_name):
    value = (model_name or "").strip()
    if value.startswith("claude-") and "/" not in value:
        return "anthropic/{0}".format(value)
    return value


def load_llm_settings():
    """Load BRD extraction LLM settings from environment variables."""
    model_name = _normalize_model_name(
        os.getenv(
            "BRD_LLM_MODEL",
            os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "gpt-4o-mini"),
        )
    )
    api_key = _resolve_api_key(
        "BRD_LLM_API_KEY",
        ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_FOUNDRY_API_KEY"),
    )
    base_url = os.getenv(
        "BRD_LLM_BASE_URL",
        os.getenv("ANTHROPIC_FOUNDRY_BASE_URL", ""),
    )
    prompt_path = Path(
        os.getenv("BRD_EXTRACTION_PROMPT_PATH", str(DEFAULT_BRD_PROMPT_PATH))
    )

    return LLMSettings(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=_read_temperature("BRD_LLM_TEMPERATURE", "0"),
        prompt_path=prompt_path,
    )


def load_brd_analyzer_mode():
    return _load_mode("BRD_ANALYZER_MODE", "hybrid")


def load_ba_llm_settings():
    """Load BA generation settings from environment variables."""
    model_name = _normalize_model_name(
        os.getenv(
            "BA_LLM_MODEL",
            os.getenv("BRD_LLM_MODEL", os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "gpt-4o-mini")),
        )
    )
    api_key = _resolve_api_key(
        "BA_LLM_API_KEY",
        (
            "BRD_LLM_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_FOUNDRY_API_KEY",
        ),
    )
    base_url = os.getenv(
        "BA_LLM_BASE_URL",
        os.getenv("BRD_LLM_BASE_URL", os.getenv("ANTHROPIC_FOUNDRY_BASE_URL", "")),
    )
    prompt_path = Path(os.getenv("BA_TASK_PROMPT_PATH", str(DEFAULT_BA_PROMPT_PATH)))

    return LLMSettings(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=_read_temperature("BA_LLM_TEMPERATURE", "0.2"),
        prompt_path=prompt_path,
    )


def load_ba_agent_mode():
    return _load_mode("BA_AGENT_MODE", "hybrid")


def load_ba_review_prompt_path():
    return Path(os.getenv("BA_REVIEW_PROMPT_PATH", str(DEFAULT_BA_REVIEW_PROMPT_PATH)))


def load_ba_review_iterations():
    return _read_iterations("BA_REVIEW_ITERATIONS", "1")


def load_sa_llm_settings():
    """Load SA generation settings from environment variables."""
    model_name = _normalize_model_name(
        os.getenv(
            "SA_LLM_MODEL",
            os.getenv("BA_LLM_MODEL", os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "gpt-4o-mini")),
        )
    )
    api_key = _resolve_api_key(
        "SA_LLM_API_KEY",
        (
            "BA_LLM_API_KEY",
            "BRD_LLM_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_FOUNDRY_API_KEY",
        ),
    )
    base_url = os.getenv(
        "SA_LLM_BASE_URL",
        os.getenv("BA_LLM_BASE_URL", os.getenv("ANTHROPIC_FOUNDRY_BASE_URL", "")),
    )
    arch_prompt_path = Path(
        os.getenv("SA_ARCH_PROMPT_PATH", str(DEFAULT_SA_ARCH_PROMPT_PATH))
    )
    dev_plan_prompt_path = Path(
        os.getenv("SA_DEV_PLAN_PROMPT_PATH", str(DEFAULT_SA_PLAN_PROMPT_PATH))
    )

    return SASettings(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=_read_temperature("SA_LLM_TEMPERATURE", "0.2"),
        architecture_prompt_path=arch_prompt_path,
        dev_plan_prompt_path=dev_plan_prompt_path,
    )


def load_sa_agent_mode():
    return _load_mode("SA_AGENT_MODE", "hybrid")


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
    return _read_iterations("SA_REVIEW_ITERATIONS", "1")


def load_dev_llm_settings():
    model_name = _normalize_model_name(
        os.getenv(
            "DEV_LLM_MODEL",
            os.getenv("SA_LLM_MODEL", os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "gpt-4o-mini")),
        )
    )
    api_key = _resolve_api_key(
        "DEV_LLM_API_KEY",
        (
            "SA_LLM_API_KEY",
            "BA_LLM_API_KEY",
            "BRD_LLM_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_FOUNDRY_API_KEY",
        ),
    )
    base_url = os.getenv(
        "DEV_LLM_BASE_URL",
        os.getenv("SA_LLM_BASE_URL", os.getenv("ANTHROPIC_FOUNDRY_BASE_URL", "")),
    )
    prompt_path = Path(
        os.getenv("DEV_CODE_PROMPT_PATH", str(DEFAULT_DEV_CODE_PROMPT_PATH))
    )

    return LLMSettings(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=_read_temperature("DEV_LLM_TEMPERATURE", "0.2"),
        prompt_path=prompt_path,
    )


def load_dev_agent_mode():
    return _load_mode("DEV_AGENT_MODE", "hybrid")


def load_dev_review_prompt_path():
    return Path(os.getenv("DEV_REVIEW_PROMPT_PATH", str(DEFAULT_DEV_REVIEW_PROMPT_PATH)))


def load_dev_review_iterations():
    return _read_iterations("DEV_REVIEW_ITERATIONS", "1")


def load_qa_llm_settings():
    model_name = _normalize_model_name(
        os.getenv(
            "QA_LLM_MODEL",
            os.getenv("DEV_LLM_MODEL", os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "gpt-4o-mini")),
        )
    )
    api_key = _resolve_api_key(
        "QA_LLM_API_KEY",
        (
            "DEV_LLM_API_KEY",
            "SA_LLM_API_KEY",
            "BA_LLM_API_KEY",
            "BRD_LLM_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_FOUNDRY_API_KEY",
        ),
    )
    base_url = os.getenv(
        "QA_LLM_BASE_URL",
        os.getenv("DEV_LLM_BASE_URL", os.getenv("ANTHROPIC_FOUNDRY_BASE_URL", "")),
    )
    prompt_path = Path(
        os.getenv("QA_PLAN_PROMPT_PATH", str(DEFAULT_QA_PLAN_PROMPT_PATH))
    )

    return LLMSettings(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=_read_temperature("QA_LLM_TEMPERATURE", "0.2"),
        prompt_path=prompt_path,
    )


def load_qa_agent_mode():
    return _load_mode("QA_AGENT_MODE", "hybrid")


def load_qa_review_prompt_path():
    return Path(os.getenv("QA_REVIEW_PROMPT_PATH", str(DEFAULT_QA_REVIEW_PROMPT_PATH)))


def load_qa_review_iterations():
    return _read_iterations("QA_REVIEW_ITERATIONS", "1")
