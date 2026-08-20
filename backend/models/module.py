"""
Pydantic models for the GitHub Repository Interconnect application.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


class EndpointType(str, Enum):
    REST_API = "rest_api"
    CLI = "cli"
    LIBRARY = "library"
    DATA_FILE = "data_file"
    DATA_STRUCTURE = "data_structure"
    DOCKER = "docker"
    WEBHOOK = "webhook"
    ML_MODEL = "ml_model"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    UNKNOWN = "unknown"


class LicenseCompatibility(str, Enum):
    PERMISSIVE = "permissive"       # MIT, Apache 2.0, BSD — freely chainable
    COPYLEFT_WEAK = "copyleft_weak" # LGPL — chainable with caution
    COPYLEFT_STRONG = "copyleft_strong"  # GPL — chain infects downstream
    PROPRIETARY = "proprietary"     # Cannot chain
    UNKNOWN = "unknown"             # No license detected


class Endpoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: EndpointType
    description: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    is_output: bool = True
    # "static" = heuristic analysis, "ai" = LLM-inferred
    source: str = "static"


class LicenseInfo(BaseModel):
    spdx_id: Optional[str] = None
    name: str = "Unknown"
    url: Optional[str] = None
    compatibility: LicenseCompatibility = LicenseCompatibility.UNKNOWN
    chain_warning: Optional[str] = None


class Module(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_url: str
    owner: str
    repo_name: str
    full_name: str          # owner/repo
    description: str = ""
    stars: int = 0
    language: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    license: LicenseInfo = Field(default_factory=LicenseInfo)
    endpoints: list[Endpoint] = Field(default_factory=list)
    is_chainable: bool = True
    caution_notes: list[str] = Field(default_factory=list)
    # UI state (position on canvas)
    position_x: float = 100.0
    position_y: float = 100.0


class Connection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_module_id: str
    source_endpoint_id: str
    target_module_id: str
    target_endpoint_id: str
    label: str = ""
    compatibility_note: Optional[str] = None


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    ANALYZING = "analyzing"
    DONE = "done"
    ERROR = "error"


class AnalysisProgress(BaseModel):
    status: AnalysisStatus
    message: str
    progress: float = 0.0  # 0–1
    module: Optional[Module] = None
    error: Optional[str] = None


class AnalyzeRequest(BaseModel):
    repo_url: str
    github_token: Optional[str] = None


class AppState(BaseModel):
    modules: list[Module] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)
