import os

from brd_agent.schemas.brd import BRDDocument, NormalizedBRD
from brd_agent.services.brd_analyzer import (
    BRDAnalysisError,
    BRDAnalyzer,
    deterministic_normalize_brd,
    normalize_brd,
)


class FakeLLMClient(object):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, system_prompt, user_prompt, temperature=0.0):
        self.calls += 1
        return self.responses.pop(0)


def _sample_document():
    return BRDDocument(
        source_path="input/sample_brd.md",
        title="Customer Support Ticket Prioritization",
        raw_markdown="# Customer Support Ticket Prioritization\n\n## Business Goal\nImprove response time.",
    )


def test_analyzer_parses_valid_json_into_schema():
    llm = FakeLLMClient(
        [
            (
                '{"project_name":"Customer Support Ticket Prioritization",'
                '"business_goal":"Improve response time",'
                '"problem_statement":"Inconsistent prioritization",'
                '"in_scope":["Intake tickets"],'
                '"open_questions":["Who owns SLA policy?"]}'
            )
        ]
    )
    analyzer = BRDAnalyzer(
        llm_client=llm,
        prompt_path="prompts/brd_extraction_prompt.md",
        temperature=0.0,
    )
    normalized = analyzer.analyze(_sample_document())

    assert isinstance(normalized, NormalizedBRD)
    assert normalized.project_name == "Customer Support Ticket Prioritization"
    assert normalized.business_goal == "Improve response time"


def test_invalid_model_output_is_handled_clearly():
    llm = FakeLLMClient(["not-json", "still-not-json"])
    analyzer = BRDAnalyzer(
        llm_client=llm,
        prompt_path="prompts/brd_extraction_prompt.md",
        temperature=0.0,
    )

    try:
        analyzer.analyze(_sample_document())
        assert False, "Expected BRDAnalysisError"
    except BRDAnalysisError as error:
        assert "invalid JSON after retry" in str(error)


def test_retry_on_invalid_json_behavior():
    os.environ["BRD_ANALYZER_MODE"] = "llm"
    llm = FakeLLMClient(
        [
            "invalid-json",
            (
                '{"project_name":"Customer Support Ticket Prioritization",'
                '"business_goal":"Improve response time",'
                '"problem_statement":"Inconsistent prioritization"}'
            ),
        ]
    )
    normalized = normalize_brd(_sample_document(), llm_client=llm)

    assert normalized.project_name == "Customer Support Ticket Prioritization"
    assert llm.calls == 2


def test_brd_hybrid_fallback_to_deterministic():
    os.environ["BRD_ANALYZER_MODE"] = "hybrid"
    llm = FakeLLMClient(["bad-output", "still-bad"])
    normalized = normalize_brd(_sample_document(), llm_client=llm)

    assert isinstance(normalized, NormalizedBRD)
    assert normalized.project_name == "Customer Support Ticket Prioritization"
    assert llm.calls == 2


def test_brd_deterministic_mode_avoids_llm():
    os.environ["BRD_ANALYZER_MODE"] = "deterministic"
    normalized = normalize_brd(_sample_document(), llm_client=FakeLLMClient([]))

    deterministic = deterministic_normalize_brd(_sample_document())
    assert normalized.project_name == deterministic.project_name
