"""Pydantic schemas for Dev implementation artifacts."""

from typing import List

from pydantic import BaseModel, Field


class DevCodeArtifact(BaseModel):
    file_path: str = ""
    language: str = ""
    purpose: str = ""
    code_snippet: str = ""


class DevPlan(BaseModel):
    implementation_summary: str = ""
    setup_steps: List[str] = Field(default_factory=list)
    module_plan: List[str] = Field(default_factory=list)
    code_artifacts: List[DevCodeArtifact] = Field(default_factory=list)
    verification_steps: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
