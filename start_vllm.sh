#!/bin/bash
# Start vLLM server with Qwen 2.5 7B Instruct and auto tool choice enabled
export VLLM_DISABLE_FLASHINFER=1
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_ATTENTION_BACKEND=FLASH_ATTN
export HF_HUB_OFFLINE=1
vllm serve cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit --port 8000 --enable-auto-tool-choice --tool-call-parser gemma4 --max-num-batched-tokens 4096 --max-model-len 8192

