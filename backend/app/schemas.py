from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal["general", "dataTransfer", "leaveAndOvertime", "approvals", "accessAndPermissions", "payroll", "billing", "other"]
Priority = Literal["normal", "high", "urgent"]
Status = Literal["open", "in_progress", "waiting_customer", "resolved", "closed"]


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class CreateTicket(Input):
    subject: str = Field(min_length=5, max_length=160)
    body: str = Field(default="", max_length=10000)
    body_html: str | None = Field(default=None, max_length=50000)
    category: Category = "general"
    priority: Priority = "normal"


class VersionInput(Input):
    version: int = Field(ge=1)


class MessageInput(VersionInput):
    body: str = Field(default="", max_length=10000)
    body_html: str | None = Field(default=None, max_length=50000)


class ReminderInput(Input):
    due_at: datetime
    note: str = Field(min_length=2, max_length=500)

    @field_validator("due_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Saat dilimi içeren bir tarih seçin.")
        return value


class AdminTicketInput(VersionInput):
    status: Status | None = None
    priority: Priority | None = None
    assigned_to: str | None = Field(default=None, max_length=36)


class DemoInput(Input):
    account: str = Field(min_length=2, max_length=40)


class LoginInput(Input):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class ExchangeInput(Input):
    code: str = Field(min_length=20, max_length=200)


class TenantInput(Input):
    active: bool | None = None
    ai_mode: Literal["inherit", "off", "draft", "auto"] | None = None


class StaffInput(Input):
    name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=5, max_length=200, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=12, max_length=200)
    role: Literal["support_agent", "platform_admin"] = "support_agent"


class StaffUpdate(Input):
    active: bool | None = None
    role: Literal["support_agent", "platform_admin"] | None = None


class PreferencesInput(Input):
    email_notifications: bool


class PasswordChangeInput(Input):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)
