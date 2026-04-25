from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# --- Generic ---

class ApiResponse(BaseModel):
    success: bool = True
    message: str = ""


# --- Bot Status ---

class BotStatusResponse(BaseModel):
    is_running: bool
    last_check_time: Optional[str] = None
    monitored_groups_count: int = 0
    admins_count: int = 0
    detected_today: int = 0


# --- Config ---

class ConfigResponse(BaseModel):
    monitoring_interval: int = 10
    history_message_count: int = 30
    llm_base_url: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 512
    llm_temperature: float = 0.0
    has_api_key: bool = False


class ConfigUpdate(BaseModel):
    monitoring_interval: Optional[int] = Field(None, ge=5, le=300)
    history_message_count: Optional[int] = Field(None, ge=5, le=100)
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_max_tokens: Optional[int] = Field(None, ge=64, le=8192)
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)


# --- Keywords ---

class KeywordList(BaseModel):
    keywords: list[str]


# --- Monitored Groups ---

class MonitoredGroupCreate(BaseModel):
    group_name: str = Field(..., min_length=1, max_length=200)


class MonitoredGroupResponse(BaseModel):
    id: int
    group_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Admins ---

class AdminCreate(BaseModel):
    admin_name: str = Field(..., min_length=1, max_length=100)
    wechat_id: str = Field(..., min_length=1, max_length=100)


class AdminResponse(BaseModel):
    id: int
    admin_name: str
    wechat_id: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Detected Messages ---

class DetectedMessageResponse(BaseModel):
    id: int
    group_name: str
    sender: str
    content: str
    matched_keyword: str
    llm_verdict: Optional[str] = None
    is_notified: bool
    detected_at: datetime

    model_config = {"from_attributes": True}


class DetectedMessageList(BaseModel):
    items: list[DetectedMessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# --- WeChat Sessions ---

class WeChatSessionResponse(BaseModel):
    name: str
    chat_type: str = ""
