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
        # Simple in-memory LRU for embeddings (size from config to limit RAM)
        self._embed_cache: dict[str, list[float]] = {}
        self._embed_keys: list[str] = []
        self._embed_capacity: int = getattr(settings, "OLLAMA_EMBED_CACHE_SIZE", 512)
    
    async def generate(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        user_message_before_context: bool = False,
    ) -> str:
        """Generate response from Ollama with configurable token limit.

        When user_message_before_context is True (large inline document excerpts), the user
        question is placed before the context blob so a small context window still sees the task.
        """
        full_prompt = self._build_prompt(
            prompt, context, system_prompt, user_message_first=user_message_before_context
        )
        
        # Use provided max_tokens or default to 2048 (standard level)
        if max_tokens is None:
            max_tokens = 2048
        
        try:
            # Check if model is available first
            try:
                check_response = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
                available_models = check_response.json().get("models", [])
                model_names = [m.get("name", "") for m in available_models]
                # Match exact or same-model tag (e.g. qwen2.5:3b matches qwen2.5:3b-q4_0), not other sizes
                model_found = self.model in model_names or any(
                    n == self.model or (n.startswith(self.model + "-") or n.startswith(self.model + ":"))
                    for n in model_names
                )
                if not model_found:
                    raise Exception(
                        f"Model '{self.model}' not found in Ollama. "
                        f"Run: ollama run {self.model}  (Available: {model_names})"
                    )
            except httpx.ConnectError as e:
                raise Exception(
                    f"Ollama is not running or not reachable at {self.base_url} (port 11434). "
                    "Start Ollama before the backend: from the LAWFIRMAI folder run RESTART_EVERYTHING.bat, "
                    "or START_OLLAMA_GPU.bat and leave that window open, then START_BACKEND.bat. "
                    f"If the model is missing: ollama pull {self.model}"
                )
            except Exception as check_error:
                raise Exception(f"Cannot connect to Ollama or model not available: {str(check_error)}")
            
            # Use longer timeout for larger models (70B gets 30 min, 14B gets 10 min, 7B gets 3 min for speed)
            if "70b" in self.model.lower():
                timeout_duration = 1800.0  # 30 minutes for 70B
            elif "14b" in self.model.lower() or "14" in self.model:
                timeout_duration = 600.0  # 10 minutes for 14B models
            elif "7b" in self.model.lower() or "7" in self.model or "law_model" in self.model.lower():
                timeout_duration = 180.0  # 3 minutes for 7B / legal models (e.g. initium/law_model)
            else:
                timeout_duration = 300.0  # 5 minutes for other models
            client = httpx.AsyncClient(timeout=timeout_duration)
            
            try:
                import time
                from server.utils.logger import setup_logger
                logger = setup_logger("ollama_service")
                logger.info(f"Generating response with {self.model} (timeout: {timeout_duration}s, max_tokens: {max_tokens})")
                start_time = time.time()

                def _build_options(include_num_gpu: bool) -> dict:
                    num_ctx = int(getattr(settings, "OLLAMA_NUM_CTX", 32768) or 32768)
                    if num_ctx < 2048:
                        num_ctx = 2048
                    o = {
                        "temperature": 0.15,
                        "top_p": 0.9,
                        "repeat_penalty": 1.2,
                        "num_predict": max_tokens,
                        "num_ctx": num_ctx,
                    }
                    if include_num_gpu:
                        if settings.OLLAMA_NUM_GPU >= 0:
                            o["num_gpu"] = settings.OLLAMA_NUM_GPU
                            logger.info(f"Ollama num_gpu={settings.OLLAMA_NUM_GPU} (CPU/split)")
                        else:
                            o["num_gpu"] = 99
                            logger.info("Ollama num_gpu=99 (NVIDIA GPU 1 only)")
                    else:
                        logger.info("Ollama generate: retry without num_gpu (Ollama runner default)")
                    return o

                last_http_error: Optional[httpx.HTTPStatusError] = None
                # Very long user context: some local models under-weight `system` vs the user blob.
                # Fold instructions into the prompt and send an empty system string.
                sys_send = system_prompt or ""
                prompt_send = full_prompt
                if context and system_prompt and len(context) > 8000:
                    prompt_send = (
                        "[Follow these instructions for your entire reply.]\n"
                        + (system_prompt or "").strip()
                        + "\n\n"
                        + self._build_prompt(
                            prompt,
                            context,
                            None,
                            user_message_first=user_message_before_context,
                        )
                    )
                    sys_send = ""

                for include_gpu in (True, False):
                    options = _build_options(include_gpu)
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": self.model,
                            "prompt": prompt_send,
                            "system": sys_send,
                            "stream": False,
                            "options": options,
                        },
                    )
                    elapsed = time.time() - start_time
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as e:
                        body = (e.response.text or "").lower()
                        if "unable to allocate cpu buffer" in body and include_gpu:
                            logger.warning("CPU buffer with num_gpu set; retrying without num_gpu in options")
                            last_http_error = e
                            continue
                        last_http_error = e
                        raise
                    logger.info(f"Ollama response received in {elapsed:.1f}s")
                    result = response.json()
                    response_text = result.get("response", "")
                    logger.info(f"Response length: {len(response_text)} characters")
                    if not response_text or not response_text.strip():
                        logger.error(f"WARNING: Ollama returned empty response! Full result: {result}")
                        raise Exception("Ollama returned an empty response. This may indicate a model issue or timeout.")
                    return response_text

                if last_http_error is not None:
                    raise last_http_error
                raise Exception("Ollama generate failed with no response")
            finally:
                await client.aclose()
        except httpx.TimeoutException:
            raise Exception(f"Ollama generation timed out. The {self.model} model may be too slow. Consider using a smaller model or increasing timeout.")
        except httpx.HTTPStatusError as e:
            body = e.response.text or ""
            # Needle must be lowercase: body.lower() contains "cpu" not "CPU"
            if "unable to allocate cpu buffer" in body.lower():
                raise Exception(
                    "Ollama HTTP error: model is loading on CPU and ran out of RAM. "
                    "Quit Ollama from the system tray, run RESTART_EVERYTHING.bat (or START_OLLAMA_GPU.bat), then start the backend. "
                    "Set OLLAMA_MODEL=tinyllama:latest in .env if you need the smallest model. "
                    f"Raw: {body[:500]}"
                )
            raise Exception(f"Ollama HTTP error: {e.response.status_code} - {body}")
        except Exception as e:
            raise Exception(f"Ollama generation error: {str(e)}")
    
    async def generate_stream(self, prompt: str, context: Optional[str] = None, system_prompt: Optional[str] = None, max_tokens: Optional[int] = None):
        """Generate streaming response with configurable token limit"""
        full_prompt = self._build_prompt(prompt, context, system_prompt)
        
        # Use provided max_tokens or default to 2048 (standard level)
        if max_tokens is None:
            max_tokens = 2048
        
        num_ctx = int(getattr(settings, "OLLAMA_NUM_CTX", 8192) or 8192)
        if num_ctx < 2048:
            num_ctx = 2048
        stream_options = {
            "temperature": 0.15,
            "top_p": 0.9,
            "repeat_penalty": 1.2,
            "num_predict": max_tokens,
            "num_ctx": num_ctx,
        }
        if settings.OLLAMA_NUM_GPU >= 0:
            stream_options["num_gpu"] = settings.OLLAMA_NUM_GPU
        else:
            stream_options["num_gpu"] = 99  # NVIDIA GPU 1 only
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "system": system_prompt,  # Send system prompt as dedicated parameter
                    "stream": True,
                    "options": stream_options,
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
    
    def _build_prompt(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_message_first: bool = False,
    ) -> str:
        """Build prompt with context only (system prompt sent separately to Ollama)."""
        parts: List[str] = []

        if user_message_first and context:
            parts.append(
                "USER REQUEST (answer this using the supporting material below; "
                "the material may be a legal PDF with OCR noise—it is not software source code "
                "unless clearly labeled as such):\n"
            )
            parts.append(f"{prompt}\n\n")
            parts.append("SUPPORTING MATERIAL:\n")
            parts.append(f"{context}\n\n")
            parts.append(
                "Now answer the USER REQUEST using only the supporting material. "
                "If the material is mostly unreadable OCR, say so plainly.\n\nAssistant:"
            )
            return "".join(parts)

        if context:
            parts.append(f"Relevant Context:\n{context}\n\n")

        parts.append(f"User Question:\n{prompt}\n\n")
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

