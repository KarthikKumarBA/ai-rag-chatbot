"""Chat model and embedding factories for openai | anthropic | bedrock."""

from app.config import Settings


def get_chat_model(settings: Settings, provider: str | None = None, model: str | None = None):
    provider = (provider or settings.llm_provider).lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        model = model or settings.openai_model_id
        if model.startswith("gpt-5"):
            # Reasoning model: low effort keeps hidden reasoning tokens small
            return ChatOpenAI(model=model, use_responses_api=True,
                              reasoning={"effort": "low"}, max_tokens=settings.max_tokens)
        return ChatOpenAI(model=model, temperature=0, max_tokens=settings.max_tokens)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model or settings.anthropic_model_id,
                             max_tokens=settings.max_tokens)

    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse

        return ChatBedrockConverse(model=model or settings.bedrock_model_id,
                                   region_name=settings.aws_region,
                                   max_tokens=settings.max_tokens)

    raise ValueError(f"Unknown LLM provider '{provider}'. Use openai, anthropic or bedrock.")


def get_embeddings(settings: Settings):
    if settings.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=settings.openai_embedding_model)

    if settings.embedding_provider == "bedrock":
        from langchain_aws import BedrockEmbeddings

        return BedrockEmbeddings(model_id=settings.bedrock_embedding_model,
                                 region_name=settings.aws_region)

    raise ValueError(
        f"Unknown embedding provider '{settings.embedding_provider}'. Use openai or bedrock."
    )


def response_text(message) -> str:
    """Plain text from any provider's response (string or content blocks)."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "") for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )
