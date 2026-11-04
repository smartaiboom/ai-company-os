"""Fixed 3.5 binding and isolated store; never upgrades a 3.1 grant or attempt."""
from dataclasses import dataclass
import os
from autonomous_gemini import GeminiStore,GeminiCompany,GeminiConfig
from gemini_provider import GeminiFreeAdapter,COST_POLICY as OLD_COST_POLICY
from ai_provider_adapter import ProviderSpec

MODEL='gemini-3.5-flash-lite'
ENDPOINT='https://generativelanguage.googleapis.com/v1beta/models/'+MODEL+':generateContent'
COST_POLICY={**OLD_COST_POLICY,'pricing_source':'https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite'}


class Gemini35Adapter(GeminiFreeAdapter):
    spec=ProviderSpec('gemini35_free',MODEL,'generate_content',ENDPOINT,'x-goog-api-key',4096,
                      'verified_free_tier_only',enabled=False)


class Gemini35Store(GeminiStore):
    mode='autonomous_gemini35_free_v2'
    marker_name='.autonomous-gemini35-free-v2-store'
    policy='gemini35_free_v2'
    project_prefix='gemini35company-'
    model=MODEL
    endpoint=ENDPOINT
    cost_policy=COST_POLICY


@dataclass(frozen=True)
class Gemini35Config(GeminiConfig):
    model:str=MODEL
    endpoint:str=ENDPOINT
    @classmethod
    def from_env(cls):
        return cls(os.getenv('GEMINI_API_KEY',''),os.getenv('GEMINI35_MODEL',''),os.getenv('GEMINI35_ENDPOINT',''))


class Gemini35Company(GeminiCompany):
    store_type=Gemini35Store
    config_type=Gemini35Config
    bound_model=MODEL
    bound_endpoint=ENDPOINT
    cost_policy=COST_POLICY
    adapter_type=Gemini35Adapter
    model_env='GEMINI35_MODEL'
    endpoint_env='GEMINI35_ENDPOINT'
    enabled_env='GEMINI35_AUTONOMOUS_FREE_ENABLED'
