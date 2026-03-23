from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class PropertyType(str, Enum):
    string = "string"
    number = "number"
    boolean = "boolean"
    date = "date"
    url = "url"
    list = "list"
    object = "object"


class PropertyInput(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=100, description="Property to look up"
    )
    type: PropertyType = Field(
        default=PropertyType.string, description="Expected value type"
    )
    description: Optional[str] = Field(default=None, max_length=500)
    examples: Optional[List[str]] = Field(
        default=None, description="Optional examples for this property"
    )


class EntityType(str, Enum):
    person = "person"
    organization = "organization"
    location = "location"
    product = "product"
    event = "event"
    other = "other"


class EntityInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Entity name")
    type: EntityType = Field(default=EntityType.other, description="Entity category")
    description: Optional[str] = Field(default=None, max_length=500)


class JobInput(BaseModel):
    properties: List[PropertyInput] = Field(..., min_length=1)
    entities: List[EntityInput] = Field(..., min_length=1)
    locale: Optional[str] = Field(
        default=None, description="Optional locale hint, e.g. en-US"
    )


class SourceRef(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None
    query: Optional[str] = None


class PropertyValue(BaseModel):
    name: str
    value: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources: List[SourceRef] = Field(default_factory=list)


class EntityResult(BaseModel):
    entity: EntityInput
    properties: List[PropertyValue]


class JobResult(BaseModel):
    results: List[EntityResult]
    queries: List[str]
