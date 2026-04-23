"""Load CampaignBrief from JSON dict or YAML string."""

import json
from typing import Any

import yaml
from campaign_schema import CampaignBrief


def parse_brief_from_dict(data: dict[str, Any]) -> CampaignBrief:
    return CampaignBrief.model_validate(data)


def parse_brief_json(s: str) -> CampaignBrief:
    return parse_brief_from_dict(json.loads(s))


def parse_brief_yaml(s: str) -> CampaignBrief:
    data = yaml.safe_load(s)
    if not isinstance(data, dict):
        raise ValueError("YAML brief must be a mapping at the root")
    return parse_brief_from_dict(data)
