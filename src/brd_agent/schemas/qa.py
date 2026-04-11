"""Pydantic schemas for QA/Test planning artifacts."""

from typing import List

from pydantic import BaseModel, Field


class QATestCase(BaseModel):
    test_id: str = ""
    title: str = ""
    test_type: str = ""
    preconditions: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    expected_results: List[str] = Field(default_factory=list)
    trace_to_requirements: List[str] = Field(default_factory=list)


class QAPlan(BaseModel):
    strategy_summary: str = ""
    test_levels: List[str] = Field(default_factory=list)
    environments: List[str] = Field(default_factory=list)
    functional_scenarios: List[str] = Field(default_factory=list)
    non_functional_scenarios: List[str] = Field(default_factory=list)
    test_cases: List[QATestCase] = Field(default_factory=list)
    automation_candidates: List[str] = Field(default_factory=list)
    quality_risks: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    exit_criteria: List[str] = Field(default_factory=list)
