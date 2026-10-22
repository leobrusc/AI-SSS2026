# Model precision: code configuration versus observed evidence
Full source/config/script search finds inference.py chooses torch.float32 on CPU and torch.float16 otherwise,
passed as torch_dtype to AutoModelForCausalLM.from_pretrained, then .to(device).eval().
No load_in_8bit/load_in_4bit, bitsandbytes, GPTQ, AWQ or quantization_config setup found.
No explicit quantization or compression pipeline is implemented in inspected loader.
This is CODE CONFIGURATION, not proof of the dtype of historical campaign tensors.
Historical CPU raw CSV does not record dtype; no real CUDA campaign tensor/dtype observation found.
The loader's resolved_revision falls back to requested revision when config._commit_hash missing;
a fallback value does not independently establish downloaded artifact provenance.
GPU run must capture parameter dtype, parameter device, config._commit_hash and requested revision directly.
