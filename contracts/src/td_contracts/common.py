from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field
from td_contracts.enums import ErrorCode

T = TypeVar("T")

class ErrorDetail(BaseModel):
    loc: List[str] = Field(default_factory=list, description="Location of the validation error")
    msg: str = Field(..., description="Error message description")
    type: str = Field(..., description="Error type identifier")

class ErrorBody(BaseModel):
    code: str = Field(..., description="Standardized error code enum string")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: List[ErrorDetail] = Field(default_factory=list, description="Detailed field or context errors")
    request_id: str = Field(..., description="Traceable correlation ID for the request")

class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorBody

class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200, description="Number of items to return")
    cursor: Optional[str] = Field(default=None, description="Opaque cursor token for next page")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list)
    next_cursor: Optional[str] = Field(default=None, description="Cursor for the next page, or null if end")
