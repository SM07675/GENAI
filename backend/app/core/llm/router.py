"""
LLM Router for Genie OS.
Uses LiteLLM to provide a unified interface to Local and Cloud models.
"""
from typing import List, Dict, Any, AsyncGenerator
import litellm
import logging

log = logging.getLogger("genie_os.llm")

# Optionally configure LiteLLM routing rules
# litellm.set_verbose = False

class LLMRouter:
    def __init__(self):
        # Default model for standard tasks
        self.default_model = "openrouter/nvidia/nemotron-3-super-120b-a12b"
        
    async def generate(self, messages: List[Dict[str, str]], model: str = None, **kwargs) -> Any:
        """Standard async generation."""
        target_model = model or self.default_model
        try:
            response = await litellm.acompletion(
                model=target_model,
                messages=messages,
                **kwargs
            )
            return response
        except Exception as e:
            log.error(f"LLM Generation failed for {target_model}: {e}")
            raise

    async def stream(self, messages: List[Dict[str, str]], model: str = None, **kwargs) -> AsyncGenerator[Any, None]:
        """Streaming async generation."""
        target_model = model or self.default_model
        try:
            response = await litellm.acompletion(
                model=target_model,
                messages=messages,
                stream=True,
                **kwargs
            )
            async for chunk in response:
                yield chunk
        except Exception as e:
            log.error(f"LLM Streaming failed for {target_model}: {e}")
            raise

    async def generate_embeddings(self, texts: List[str], model: str = "text-embedding-3-small") -> List[List[float]]:
        """Generate embeddings using LiteLLM."""
        try:
            response = await litellm.aembedding(
                model=model,
                input=texts
            )
            return [data['embedding'] for data in response['data']]
        except Exception as e:
            log.error(f"Embedding generation failed: {e}")
            raise

llm_router = LLMRouter()
