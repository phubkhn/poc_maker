"""Pydantic schemas for SA planning artifacts."""

from typing import List

from pydantic import BaseModel, Field


class SAComponent(BaseModel):
    name: str = ""
    responsibility: str = ""
    interfaces: List[str] = Field(default_factory=list)


class SAArchitecturePlan(BaseModel):
    system_overview: str = ""
    goals_and_constraints: List[str] = Field(default_factory=list)
    high_level_architecture: str = ""
    architecture_decisions: List[str] = Field(default_factory=list)
    components: List[SAComponent] = Field(default_factory=list)
    data_flow: List[str] = Field(default_factory=list)
    integration_points: List[str] = Field(default_factory=list)
    external_integrations: List[str] = Field(default_factory=list)
    data_storage_considerations: List[str] = Field(default_factory=list)
    security_considerations: List[str] = Field(default_factory=list)
    observability_considerations: List[str] = Field(default_factory=list)
    non_functional_considerations: List[str] = Field(default_factory=list)
    risks_and_tradeoffs: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)


class SADevelopmentPlan(BaseModel):
    implementation_strategy: str = ""
    development_phases: List[str] = Field(default_factory=list)
    deliverables_by_phase: List[str] = Field(default_factory=list)
    module_breakdown: List[str] = Field(default_factory=list)
    implementation_order: List[str] = Field(default_factory=list)
    risks_and_dependencies: List[str] = Field(default_factory=list)
    testing_considerations: List[str] = Field(default_factory=list)
    rollout_and_release_notes: List[str] = Field(default_factory=list)
    clarification_items: List[str] = Field(default_factory=list)
