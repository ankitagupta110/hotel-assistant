import os
from time import perf_counter

import httpx
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from config import settings
from rag.prompt import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE
from utils.logger import logger


class LLMClient:
    def __init__(self) -> None:
        self.provider = (settings.llm_provider or "auto").lower()
        self.openai_client = self._build_openai_client()
        self.provider_order = self._build_provider_order()

    def generate_rag_answer(self, question: str, context: str) -> str:
        user_prompt = RAG_USER_TEMPLATE.format(context=context, question=question)
        for provider in self.provider_order:
            answer = self._generate_with_provider(provider, user_prompt)
            if answer:
                return answer

        return self._fallback_answer(question, context)

    def _build_openai_client(self) -> OpenAI | None:
        if not settings.openai_api_key:
            return None
        try:
            return OpenAI(
                api_key=settings.openai_api_key,
                max_retries=2,
            )
        except Exception as exc:
            logger.warning("OpenAI client initialization failed: %s", exc)
            return None

    def _build_provider_order(self) -> list[str]:
        providers = ["huggingface", "openai", "ollama"]
        if self.provider in providers:
            ordered = [self.provider]
        else:
            ordered = providers
        return [provider for provider in ordered if self._is_provider_configured(provider)]

    def _is_provider_configured(self, provider: str) -> bool:
        if provider == "openai":
            return self.openai_client is not None
        if provider == "huggingface":
            return bool(settings.huggingface_api_key and settings.huggingface_model)
        if provider == "ollama":
            if self.provider == "ollama":
                return bool(settings.ollama_base_url and settings.ollama_model)
            return bool(os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_MODEL"))
        return False

    def _generate_with_provider(self, provider: str, user_prompt: str) -> str:
        if provider == "openai":
            return self._generate_with_openai(user_prompt)
        if provider == "huggingface":
            return self._generate_with_huggingface(user_prompt)
        if provider == "ollama":
            return self._generate_with_ollama(user_prompt)
        return ""

    def _generate_with_openai(self, user_prompt: str) -> str:
        if not self.openai_client:
            return ""

        started_at = perf_counter()
        try:
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": RAG_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=180,
                temperature=0.1,
            )
            content = response.choices[0].message.content
            if content:
                logger.info(
                    "LLM openai | model=%s | total=%.2f ms",
                    settings.openai_model,
                    (perf_counter() - started_at) * 1000,
                )
                return content.strip()
        except RateLimitError as exc:
            logger.warning("OpenAI rate limit reached, trying fallback provider: %s", exc)
        except (APIConnectionError, APITimeoutError) as exc:
            logger.warning("OpenAI request failed, trying fallback provider: %s", exc)
        except Exception as exc:
            logger.warning("OpenAI generation failed, trying fallback provider: %s", exc)
        return ""

    def _generate_with_huggingface(self, user_prompt: str) -> str:
        if not settings.huggingface_api_key:
            return ""

        payload = {
            "inputs": f"<|system|>\n{RAG_SYSTEM_PROMPT}\n<|user|>\n{user_prompt}\n<|assistant|>",
            "parameters": {"max_new_tokens": 180, "temperature": 0.1, "return_full_text": False},
        }

        started_at = perf_counter()
        try:
            response = httpx.post(
                f"https://api-inference.huggingface.co/models/{settings.huggingface_model}",
                headers={"Authorization": f"Bearer {settings.huggingface_api_key}"},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                logger.info(
                    "LLM huggingface | model=%s | total=%.2f ms",
                    settings.huggingface_model,
                    (perf_counter() - started_at) * 1000,
                )
                return str(data[0].get("generated_text", "")).strip()
            if isinstance(data, dict):
                logger.info(
                    "LLM huggingface | model=%s | total=%.2f ms",
                    settings.huggingface_model,
                    (perf_counter() - started_at) * 1000,
                )
                return str(data.get("generated_text", "")).strip()
        except Exception as exc:
            logger.warning("Hugging Face generation failed, trying fallback provider: %s", exc)

        return ""

    def _generate_with_ollama(self, user_prompt: str) -> str:
        started_at = perf_counter()
        try:
            response = httpx.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": f"{RAG_SYSTEM_PROMPT}\n\n{user_prompt}",
                    "stream": False,
                    "keep_alive": settings.ollama_keep_alive,
                    "options": {
                        "num_predict": settings.ollama_num_predict,
                        "temperature": 0.1,
                    },
                },
                timeout=settings.ollama_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                logger.info(
                    (
                        "LLM ollama | model=%s | total=%.2f ms | ollama_total=%.2f ms "
                        "| load=%.2f ms | prompt_eval=%.2f ms | eval=%.2f ms | eval_count=%s"
                    ),
                    settings.ollama_model,
                    (perf_counter() - started_at) * 1000,
                    self._ns_to_ms(data.get("total_duration")),
                    self._ns_to_ms(data.get("load_duration")),
                    self._ns_to_ms(data.get("prompt_eval_duration")),
                    self._ns_to_ms(data.get("eval_duration")),
                    data.get("eval_count", 0),
                )
                text = data.get("response", "")
                if text:
                    return str(text).strip()
        except Exception as exc:
            logger.warning("Ollama generation failed, using local fallback: %s", exc)
        return ""

    @staticmethod
    def _ns_to_ms(value: object) -> float:
        if not isinstance(value, (int, float)):
            return 0.0
        return float(value) / 1_000_000

    def _fallback_answer(self, question: str, context: str) -> str:
        context_text = " ".join(context.split())
        if not context_text:
            return "I couldn't find that information in the hotel guide."

        if question.strip().lower().startswith(("what", "when", "where", "who", "how")):
            return f"Based on the hotel guide: {context_text[:400]}"
        return context_text[:400]


llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global llm_client
    if llm_client is None:
        llm_client = LLMClient()
    return llm_client
