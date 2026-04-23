from pydantic import BaseModel, Field, field_validator


class Product(BaseModel):
    id: str = Field(min_length=1, description="Directory-safe product slug")
    name: str = Field(min_length=1, description="Display name for prompts")


class CampaignBrief(BaseModel):
    """Request body for POST /generate/campaign (see README sample JSON)."""

    campaign_name: str | None = None
    products: list[Product] = Field(
        min_length=2, description="At least two products per brief"
    )
    target_region: str
    target_audience: str
    campaign_message: str = Field(min_length=1, description="On-image text (English)")
    overlay_locale: str | None = Field(
        default=None,
        description='Optional: "es" (or "Spanish") to render Spanish on-image text via Claude',
    )

    @field_validator("products")
    @classmethod
    def at_least_two(cls, v: list[Product]) -> list[Product]:
        if len(v) < 2:
            raise ValueError("At least 2 products are required")
        return v
