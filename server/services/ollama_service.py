"""
Ollama service - Handles LLM interactions
"""
import httpx
import json
from typing import List, Dict, Optional
from server.config import settings


class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        # Increased timeout for 70B model (can take longer to generate)
        # 70B models are slower, so we need more time
        timeout_duration = 1800.0 if "70b" in self.model.lower() else 300.0
        self.client = httpx.AsyncClient(timeout=timeout_duration)
        # Simple in-memory LRU for embeddings
        self._embed_cache: dict[str, list[float]] = {}
        self._embed_keys: list[str] = []
        self._embed_capacity: int = 4096  # Increased from 1024 to leverage 32GB RAM
    
    async def generate(self, prompt: str, context: Optional[str] = None, system_prompt: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        """Generate response from Ollama with configurable token limit"""
        full_prompt = self._build_prompt(prompt, context, system_prompt)
        
        # Use provided max_tokens or default to 2048 (standard level)
        if max_tokens is None:
            max_tokens = 2048
        
        try:
            # Check if model is available first
            try:
                check_response = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
                available_models = check_response.json().get("models", [])
                model_names = [m.get("name", "") for m in available_models]
                if self.model not in model_names:
                    raise Exception(f"Model '{self.model}' not found in Ollama. Available models: {model_names}")
            except Exception as check_error:
                raise Exception(f"Cannot connect to Ollama or model not available: {str(check_error)}")
            
            # Use longer timeout for larger models (70B gets 30 min, 14B gets 10 min, 7B gets 3 min for speed)
            if "70b" in self.model.lower():
                timeout_duration = 1800.0  # 30 minutes for 70B
            elif "14b" in self.model.lower() or "14" in self.model:
                timeout_duration = 600.0  # 10 minutes for 14B models
            elif "7b" in self.model.lower() or "7" in self.model:
                timeout_duration = 180.0  # 3 minutes for 7B models (faster responses)
            else:
                timeout_duration = 300.0  # 5 minutes for other models
            client = httpx.AsyncClient(timeout=timeout_duration)
            
            try:
                import time
                from server.utils.logger import setup_logger
                logger = setup_logger("ollama_service")
                logger.info(f"Generating response with {self.model} (timeout: {timeout_duration}s, max_tokens: {max_tokens})")
                start_time = time.time()
                
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": full_prompt,
                        "system": system_prompt,  # Send system prompt as dedicated parameter
                        "stream": False,
                        "options": {
                            "temperature": 0.15,
                            "top_p": 0.9,
                            "repeat_penalty": 1.2,
                            "num_predict": max_tokens  # Dynamic token limit
                        }
                    }
                )
                elapsed = time.time() - start_time
                logger.info(f"Ollama response received in {elapsed:.1f}s")
                response.raise_for_status()
                result = response.json()
                response_text = result.get("response", "")
                logger.info(f"Response length: {len(response_text)} characters")
                
                # Validate response is not empty
                if not response_text or not response_text.strip():
                    logger.error(f"WARNING: Ollama returned empty response! Full result: {result}")
                    raise Exception("Ollama returned an empty response. This may indicate a model issue or timeout.")
                
                return response_text
            finally:
                await client.aclose()
        except httpx.TimeoutException:
            raise Exception(f"Ollama generation timed out. The {self.model} model may be too slow. Consider using a smaller model or increasing timeout.")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Ollama generation error: {str(e)}")
    
    async def generate_stream(self, prompt: str, context: Optional[str] = None, system_prompt: Optional[str] = None, max_tokens: Optional[int] = None):
        """Generate streaming response with configurable token limit"""
        full_prompt = self._build_prompt(prompt, context, system_prompt)
        
        # Use provided max_tokens or default to 2048 (standard level)
        if max_tokens is None:
            max_tokens = 2048
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "system": system_prompt,  # Send system prompt as dedicated parameter
                    "stream": True,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_predict": max_tokens  # Dynamic token limit
                    }
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if "response" in chunk:
                                yield chunk["response"]
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
    
    def _build_prompt(self, prompt: str, context: Optional[str] = None, system_prompt: Optional[str] = None) -> str:
        """Build prompt with context only (system prompt sent separately)"""
        parts = []
        
        # Note: system_prompt is now handled by the 'system' parameter in the API call
        # and doesn't need to be prepended here, avoiding confusion.
        
        if context:
            parts.append(f"Relevant Context:\n{context}\n\n")
        
        # Force the 10-box structure reminder at the very end
        structure_reminder = (
            "\nIMPORTANT: You must strictly follow the requested 10-box response format defined in your system instructions.\n"
            "Do not output standard text paragraphs. Use the headers above."
        )
        
        parts.append(f"User Question:\n{prompt}\n{structure_reminder}\n\n")
        parts.append("Response:")
        
        return "".join(parts)
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using Ollama"""
        # Cache first
        key = text[:2000]  # cap key size
        if key in self._embed_cache:
            return self._embed_cache[key]
        try:
            response = await self.client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": settings.OLLAMA_EMBEDDING_MODEL,
                    "prompt": text
                }
            )
            response.raise_for_status()
            result = response.json()
            emb = result.get("embedding", [])
            # Save to cache
            if emb:
                self._embed_cache[key] = emb
                self._embed_keys.append(key)
                if len(self._embed_keys) > self._embed_capacity:
                    old = self._embed_keys.pop(0)
                    self._embed_cache.pop(old, None)
            return emb
        except Exception as e:
            raise Exception(f"Ollama embedding error: {str(e)}")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


ollama_service = OllamaService()

