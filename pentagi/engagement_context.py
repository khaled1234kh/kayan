"""Optional descriptive intake. Never merge this data into the signed ROE."""
from pydantic import BaseModel, ConfigDict, Field

CONTEXT_LABEL = 'Descriptive context only — zero policy weight; not scope, authorization or verified evidence.'


class EngagementContext(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    company_size: str = Field(default='', max_length=2000)
    departments: str = Field(default='', max_length=4000)
    infrastructure_summary: str = Field(default='', max_length=12000)
    network_architecture: str = Field(default='', max_length=12000)
    data_storage: str = Field(default='', max_length=12000)
    customer_touchpoints: str = Field(default='', max_length=12000)


def descriptive_context(value=None):
    context = value if isinstance(value, EngagementContext) else EngagementContext.model_validate(value or {})
    # Omit blank optional fields, but never alter an entered description.
    return {k:v for k,v in context.model_dump().items() if v.strip()}
