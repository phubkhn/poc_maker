"""BRD analyzer with deterministic and LiteLLM extraction modes."""

import json
from pathlib import Path

from pydantic import ValidationError

from brd_agent.config import load_brd_analyzer_mode, load_llm_settings
from brd_agent.llm.client import LiteLLMClient
from brd_agent.schemas.brd import NormalizedBRD


class BRDAnalysisError(Exception):
    """Raised when BRD analysis fails after retry and validation."""


def _parse_bullets(section_text):
    items = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _split_sections(markdown_text):
    sections = {}
    current_section = None
    buffer_lines = []

    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_section is not None:
                sections[current_section] = "\n".join(buffer_lines).strip()
            current_section = stripped[3:].strip().lower()
            buffer_lines = []
        else:
            buffer_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(buffer_lines).strip()
    return sections


def _strip_json_code_fence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


class BRDAnalyzer(object):
    """LLM-backed BRD analyzer with one retry for invalid JSON."""

    def __init__(self, llm_client, prompt_path, temperature=0.0):
        self.llm_client = llm_client
        self.prompt_path = Path(prompt_path)
        self.temperature = temperature

    def analyze(self, brd_document):
        system_prompt = self._load_system_prompt()
        user_prompt = self._build_user_prompt(brd_document.raw_markdown)

        first_response = self.llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
        )

        try:
            return self._parse_and_validate(first_response)
        except ValueError as parse_error:
            repair_prompt = self._build_repair_prompt(
                brd_document.raw_markdown,
                first_response,
                str(parse_error),
            )
            repair_response = self.llm_client.complete(
                system_prompt=system_prompt,
                user_prompt=repair_prompt,
                temperature=0.0,
            )
            try:
                return self._parse_and_validate(repair_response)
            except ValueError as second_parse_error:
                raise BRDAnalysisError(
                    "LLM returned invalid JSON after retry: {0}".format(
                        second_parse_error
                    )
                )
            except ValidationError as validation_error:
                raise BRDAnalysisError(
                    "LLM returned JSON but schema validation failed after retry: {0}".format(
                        validation_error
                    )
                )
        except ValidationError as validation_error:
            raise BRDAnalysisError(
                "LLM returned JSON but schema validation failed: {0}".format(
                    validation_error
                )
            )

    def _load_system_prompt(self):
        if not self.prompt_path.exists():
            raise BRDAnalysisError(
                "Prompt file not found: {0}".format(self.prompt_path)
            )
        return self.prompt_path.read_text(encoding="utf-8")

    def _build_user_prompt(self, raw_markdown):
        return (
            "BRD source:\n"
            "{0}\n\n"
            "Schema JSON for reference:\n"
            "{1}\n"
        ).format(raw_markdown, NormalizedBRD.schema_json(indent=2))

    def _build_repair_prompt(self, raw_markdown, invalid_output, error_message):
        return (
            "Your previous output was invalid JSON.\n"
            "Error: {0}\n\n"
            "Return ONLY valid JSON for this schema:\n"
            "{1}\n\n"
            "Original BRD source:\n"
            "{2}\n\n"
            "Previous output to repair:\n"
            "{3}\n"
        ).format(
            error_message,
            NormalizedBRD.schema_json(indent=2),
            raw_markdown,
            invalid_output,
        )

    @staticmethod
    def _parse_and_validate(raw_output):
        cleaned = _strip_json_code_fence(raw_output)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise ValueError(str(error))
        return NormalizedBRD.parse_obj(payload)


def deterministic_normalize_brd(brd_document):
    """Deterministic section parser used as fallback and non-LLM mode."""
    sections = _split_sections(brd_document.raw_markdown)
    in_scope = _parse_bullets(sections.get("scope", ""))
    constraints = _parse_bullets(sections.get("constraints", ""))
    success_metrics = _parse_bullets(sections.get("success metrics", ""))

    if not in_scope and sections.get("scope", "").strip():
        in_scope = [sections.get("scope", "").strip()]
    if not constraints and sections.get("constraints", "").strip():
        constraints = [sections.get("constraints", "").strip()]
    if not success_metrics and sections.get("success metrics", "").strip():
        success_metrics = [sections.get("success metrics", "").strip()]

    return NormalizedBRD(
        project_name=brd_document.title,
        business_goal=sections.get("business goal", ""),
        problem_statement=sections.get(
            "problem statement", "Problem statement not explicitly provided in BRD."
        ),
        in_scope=in_scope,
        features=list(in_scope),
        functional_requirements=list(in_scope),
        constraints=constraints,
        acceptance_criteria=success_metrics,
        assumptions=["Current support channels and ticket data are accessible."],
        outputs=["Prioritized tickets with assigned resolver group."],
        open_questions=[
            "Who are the primary actors and their responsibilities?",
            "What exact inputs and outputs are required for prioritization?",
            "Which non-functional requirements (latency, reliability, audit) are mandatory?",
        ],
    )


def normalize_brd(brd_document, llm_client=None):
    """Normalize a BRD document with selected mode (deterministic/llm/hybrid)."""
    mode = load_brd_analyzer_mode()
    if mode == "deterministic":
        return deterministic_normalize_brd(brd_document)

    settings = load_llm_settings()
    client = llm_client or LiteLLMClient(
        model_name=settings.model_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
    )
    analyzer = BRDAnalyzer(
        llm_client=client,
        prompt_path=settings.prompt_path,
        temperature=settings.temperature,
    )
    if mode == "llm":
        return analyzer.analyze(brd_document)

    # hybrid mode
    try:
        return analyzer.analyze(brd_document)
    except BRDAnalysisError:
        return deterministic_normalize_brd(brd_document)
