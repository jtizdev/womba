"""
AI client factory for creating OpenAI and Anthropic clients.
Single Responsibility: AI client creation and configuration.
"""

from typing import Optional, Union
from loguru import logger

from src.config.settings import settings


class AIClientFactory:
    """
    Factory for creating AI client instances.
    Supports OpenAI and Anthropic (Claude) clients.
    """

    @staticmethod
    def create_openai_client(api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Create OpenAI client.
        
        Args:
            api_key: Optional API key (uses settings default if not provided)
            model: Optional model name (uses settings default if not provided)
            
        Returns:
            Tuple of (client, model_name)
        """
        from openai import OpenAI
        
        api_key = api_key or settings.openai_api_key
        model = model or settings.ai_model
        
        client = OpenAI(api_key=api_key)
        logger.info(f"Created OpenAI client with model: {model}")
        
        return client, model

    @staticmethod
    def create_anthropic_client(api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Create Anthropic (Claude) client.
        
        Args:
            api_key: Optional API key (uses settings default if not provided)
            model: Optional model name (uses settings default if not provided)
            
        Returns:
            Tuple of (client, model_name)
        """
        from anthropic import Anthropic
        
        api_key = api_key or settings.anthropic_api_key
        model = model or settings.default_ai_model
        
        client = Anthropic(api_key=api_key)
        logger.info(f"Created Anthropic client with model: {model}")
        
        return client, model

    @staticmethod
    def create_client(
        use_openai: bool = True,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Create AI client based on provider preference.
        
        Args:
            use_openai: Whether to use OpenAI (True) or Anthropic (False)
            api_key: Optional API key
            model: Optional model name
            
        Returns:
            Tuple of (client, model_name, use_openai)
        """
        if use_openai:
            client, model = AIClientFactory.create_openai_client(api_key, model)
            return client, model, True
        else:
            client, model = AIClientFactory.create_anthropic_client(api_key, model)
            return client, model, False

