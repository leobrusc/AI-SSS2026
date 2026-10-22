"""GPT-2 inference engine with async support."""

import asyncio
import functools
from pathlib import Path
from typing import Any, Optional

from traceai.logging_config import get_logger

logger = get_logger("service.inference")


class InferenceEngine:
    """Manages GPT-2 model loading and text generation."""

    def __init__(
        self,
        model_id: str = "openai-community/gpt2",
        model_dir: Optional[str] = None,
        device: str = "auto",
        max_new_tokens: int = 100,
        revision: Optional[str] = None,
    ):
        self.model_id = model_id
        self.model_dir = model_dir
        self._device_config = device
        self.max_new_tokens = max_new_tokens
        self.revision = revision
        self._model = None
        self._tokenizer = None
        self._device_resolved = None
        self._resolved_revision = None
        self.is_loaded = False

    async def load(self) -> None:
        """Load model and tokenizer."""
        logger.info(f"Loading model: {self.model_id}")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_sync)

        self.is_loaded = True
        logger.info(f"Model loaded on device: {self._device_resolved}")

    def _load_sync(self) -> None:
        """Synchronous model loading."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # Resolve device
        if self._device_config == "auto":
            self._device_resolved = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device_resolved = self._device_config

        # Determine model source
        model_source = self.model_dir if self.model_dir else self.model_id

        logger.info(f"Loading from: {model_source}")
        logger.info(f"Target device: {self._device_resolved}")

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_source,
            revision=self.revision,
            padding_side="left",
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        dtype = torch.float32 if self._device_resolved == "cpu" else torch.float16
        self._model = AutoModelForCausalLM.from_pretrained(
            model_source,
            revision=self.revision,
            torch_dtype=dtype,
        ).to(self._device_resolved).eval()

        # Resolve the actual revision from the loaded model config
        self._resolved_revision = getattr(self._model.config, "_commit_hash", None)

    @property
    def parameter_device(self) -> str:
        return str(next(self._model.parameters()).device) if self._model is not None else "unknown"

    @property
    def parameter_dtype(self) -> str:
        return str(next(self._model.parameters()).dtype) if self._model is not None else "unknown"

    async def generate(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: float = 1.0,
        seed: Optional[int] = None,
    ) -> dict[str, Any]:
        """Generate text from a prompt asynchronously."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            functools.partial(
                self._generate_sync,
                prompt=prompt,
                max_new_tokens=max_new_tokens or self.max_new_tokens,
                temperature=temperature,
                seed=seed,
            ),
        )
        return result

    def _generate_sync(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
        seed: Optional[int],
    ) -> dict[str, Any]:
        """Synchronous text generation."""
        import torch

        if seed is not None:
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed(seed)

        inputs = self._tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=512
        )
        inputs = {k: v.to(self._device_resolved) for k, v in inputs.items()}
        input_length = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature if temperature != 1.0 else None,
                do_sample=temperature != 1.0,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        generated_ids = outputs[0][input_length:]
        text = self._tokenizer.decode(generated_ids, skip_special_tokens=True)
        tokens_generated = len(generated_ids)

        return {
            "text": text,
            "tokens_generated": tokens_generated,
        }

    async def unload(self) -> None:
        """Unload model and free resources."""
        if self._model is not None:
            import torch
            del self._model
            del self._tokenizer
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self._model = None
            self._tokenizer = None
            self.is_loaded = False
            logger.info("Model unloaded")

    @property
    def device(self) -> str:
        """Return the resolved device string."""
        return self._device_resolved or self._device_config

    @property
    def resolved_revision(self) -> Optional[str]:
        """Return the resolved model revision (commit hash from HF Hub)."""
        return self._resolved_revision
