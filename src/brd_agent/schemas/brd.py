"""Pydantic schemas for BRD loading and normalized output."""

from typing import List

from pydantic import BaseModel, Field


class BRDDocument(BaseModel):
    """Raw BRD document loaded from disk."""

    source_path: str = Field(..., description="Original BRD file path.")
    title: str = Field(..., description="Derived BRD title.")
    raw_markdown: str = Field(..., description="Raw BRD markdown content.")


class NormalizedBRD(BaseModel):
    """Normalized BRD schema used for artifact generation."""

    project_name: str = ""
    business_goal: str = ""
    problem_statement: str = ""
    in_scope: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)
    actors: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    functional_requirements: List[str] = Field(default_factory=list)
    non_functional_requirements: List[str] = Field(default_factory=list)
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
