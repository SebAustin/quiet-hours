from strands.models.bedrock import BedrockModel

from quiet.config import load_settings


def load_model(kind: str = "smart") -> BedrockModel:
    """Bedrock model client using IAM credentials. 'fast' for triage/chat, 'smart' for specialists."""
    settings = load_settings()
    model_id = settings.fast_model if kind == "fast" else settings.smart_model
    return BedrockModel(model_id=model_id, region_name=settings.region, temperature=0.2)
