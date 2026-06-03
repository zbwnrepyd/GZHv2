"""层3：Pydantic 验证层 — 写库前拦截非法枚举值"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, field_validator

AI_MODEL_VALUES = {'proprietary_model', 'fine_tuned', 'multi_model', 'openai_only', 'no_ai_core'}
WORKFLOW_VALUES = {'system_of_record', 'workflow_embedded', 'plugin_addon', 'standalone_tool'}
FLYWHEEL_VALUES = {'yes', 'partial', 'no'}
DATA_ASSET_VALUES = {'yes_core', 'yes_supplementary', 'no'}
INCUMBENT_VALUES = {'openai', 'google', 'microsoft', 'multiple', 'other', 'none'}
CUSTOMER_VALUES = {'b2b_enterprise', 'b2b_smb', 'developer_api', 'b2b2c', 'b2c'}
PRICING_VALUES = {'outcome_based', 'enterprise_contract', 'subscription', 'usage_based', 'freemium', 'free'}
INFERENCE_VALUES = {'high', 'medium', 'low', 'none'}
STACK_VALUES = {'infrastructure', 'foundation_model', 'middleware', 'vertical_app', 'distribution'}


class CompetitiveFields(BaseModel):
    ai_model_dependency: Optional[str] = None
    workflow_integration_level: Optional[str] = None
    data_flywheel: Optional[str] = None
    proprietary_data_asset: Optional[str] = None
    incumbent_direct_competitor: Optional[str] = None
    customer_segment_type: Optional[str] = None
    pricing_model: Optional[str] = None
    inference_cost_exposure: Optional[str] = None
    stack_layer: Optional[str] = None

    @field_validator('ai_model_dependency')
    @classmethod
    def v_ai_model(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if v not in AI_MODEL_VALUES:
            raise ValueError(f'ai_model_dependency={v} not in {AI_MODEL_VALUES}')
        return v

    @field_validator('workflow_integration_level')
    @classmethod
    def v_workflow(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if v not in WORKFLOW_VALUES:
            raise ValueError(f'workflow_integration_level={v} not in {WORKFLOW_VALUES}')
        return v

    @field_validator('data_flywheel')
    @classmethod
    def v_flywheel(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if v not in FLYWHEEL_VALUES:
            raise ValueError(f'data_flywheel={v} not in {FLYWHEEL_VALUES}')
        return v

    @field_validator('proprietary_data_asset')
    @classmethod
    def v_data_asset(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if v not in DATA_ASSET_VALUES:
            raise ValueError(f'proprietary_data_asset={v} not in {DATA_ASSET_VALUES}')
        return v

    @field_validator('incumbent_direct_competitor')
    @classmethod
    def v_incumbent(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if v not in INCUMBENT_VALUES:
            raise ValueError(f'incumbent_direct_competitor={v} not in {INCUMBENT_VALUES}')
        return v

    @field_validator('customer_segment_type')
    @classmethod
    def v_customer(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if v not in CUSTOMER_VALUES:
            raise ValueError(f'customer_segment_type={v} not in {CUSTOMER_VALUES}')
        return v

    @field_validator('pricing_model')
    @classmethod
    def v_pricing(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if v not in PRICING_VALUES:
            raise ValueError(f'pricing_model={v} not in {PRICING_VALUES}')
        return v

    @field_validator('inference_cost_exposure')
    @classmethod
    def v_inference(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if v not in INFERENCE_VALUES:
            raise ValueError(f'inference_cost_exposure={v} not in {INFERENCE_VALUES}')
        return v

    @field_validator('stack_layer')
    @classmethod
    def v_stack(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if v not in STACK_VALUES:
            raise ValueError(f'stack_layer={v} not in {STACK_VALUES}')
        return v


def validate_enum_fields(raw: dict) -> dict:
    """验证并返回干净的枚举字段。非法值抛 ValueError；缺字段填 None。"""
    fields = {f: raw.get(f) for f in CompetitiveFields.model_fields}
    validated = CompetitiveFields(**fields)
    return {k: v for k, v in validated.model_dump().items() if v is not None}
