import os
from langchain_core.language_models.chat_models import BaseChatModel
from ..base import BaseLLMProvider

class BedrockProvider(BaseLLMProvider):
    name = "bedrock"

    def supports_thinking(self) -> bool:
        # Returns True if the selected execution model is a known reasoning/thinking model
        model_name = os.getenv("MODEL_EXEC_BEDROCK", "").lower()
        return "r1" in model_name or "thinking" in model_name or "reasoning" in model_name

    def _get_bedrock_client(self):
        """
        Creates a boto3 bedrock-runtime client with credentials from env or AWS configuration.
        Supports both AWS_BEARER_TOKEN_BEDROCK and standard IAM credentials.
        """
        try:
            import boto3
        except ImportError:
            raise ImportError("Please install boto3 and langchain-aws to use Amazon Bedrock.")

        bearer_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        region_name = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "us-east-1"
        profile_name = os.getenv("AWS_PROFILE")

        session_kwargs = {}
        if profile_name:
            session_kwargs["profile_name"] = profile_name
        if region_name:
            session_kwargs["region_name"] = region_name

        # If bearer token is present, we do not pass standard IAM credentials
        # to avoid conflicts, allowing boto3 to use bearer token authentication automatically.
        if not bearer_token:
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_session_token = os.getenv("AWS_SESSION_TOKEN")

            if aws_access_key:
                session_kwargs["aws_access_key_id"] = aws_access_key
            if aws_secret_key:
                session_kwargs["aws_secret_access_key"] = aws_secret_key
            if aws_session_token:
                session_kwargs["aws_session_token"] = aws_session_token

        session = boto3.Session(**session_kwargs)
        return session.client("bedrock-runtime", region_name=region_name)

    def create_router_llm(self) -> BaseChatModel:
        try:
            from langchain_aws import ChatBedrockConverse
        except ImportError:
            from langchain_aws import ChatBedrock as ChatBedrockConverse

        model_name = os.getenv("MODEL_ROUTER_BEDROCK", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

        return ChatBedrockConverse(
            model_id=model_name,
            client=self._get_bedrock_client(),
            temperature=0.1,
        )

    def create_execution_llm(self, use_thinking: bool = False) -> BaseChatModel:
        try:
            from langchain_aws import ChatBedrockConverse
        except ImportError:
            from langchain_aws import ChatBedrock as ChatBedrockConverse

        model_name = os.getenv("MODEL_EXEC_BEDROCK", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

        return ChatBedrockConverse(
            model_id=model_name,
            client=self._get_bedrock_client(),
            temperature=0.1,
        )

    def create_vision_llm(self) -> BaseChatModel:
        try:
            from langchain_aws import ChatBedrockConverse
        except ImportError:
            from langchain_aws import ChatBedrock as ChatBedrockConverse

        model_name = os.getenv("MODEL_ROUTER_BEDROCK", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

        return ChatBedrockConverse(
            model_id=model_name,
            client=self._get_bedrock_client(),
            temperature=0.2,
        )
