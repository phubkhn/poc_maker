"""Pydantic schemas for BA planning artifacts."""

from typing import List

from pydantic import BaseModel, Field


class BATask(BaseModel):
    title: str = ""
    description: str = ""
    module_hint: str = ""
    dependency_notes: List[str] = Field(default_factory=list)
    risk_notes: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)


class BAEpic(BaseModel):
    name: str = ""
    objective: str = ""
    summary: str = ""
    out_of_scope_notes: List[str] = Field(default_factory=list)
    tasks: List[BATask] = Field(default_factory=list)


class BAPlan(BaseModel):
    project_summary: str = ""
    scope_summary: str = ""
    implementation_notes: List[str] = Field(default_factory=list)
    epics: List[BAEpic] = Field(default_factory=list)
    cross_epic_dependencies: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
