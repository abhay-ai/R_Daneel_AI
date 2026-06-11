# R_Daneel_AI 🤖

> **"Our goal is not to control the LLM, but to show direction when it is confused."**

Welcome to **R_Daneel_AI** (named after Isaac Asimov's robot character *R. Daneel Olivaw*). This is a state-of-the-art **Neuro-Symbolic Chess Bot** and **LLM Chess Benchmarking Suite** that blends the strategic vision of Large Language Models (LLMs) with the rigid logical validation of pure Prolog constraints.

---

## 🌟 Interactive Documentation & Landing Pages

For a premium, interactive viewing experience, open these files in your web browser:
1. **Landing Page & Feature Overview**: [docs/index.html](docs/index.html) - Features an interactive chess playground showing the bot's thoughts, active strategy plans, and decision metrics across scenarios.
2. **Interactive Developer Setup Guide**: [docs/readme.html](docs/readme.html) - Step-by-step setup guide covering environment configuration, local vLLM MoE GPU serving parameters, test runs, and troubleshooting.

---

## 🧠 Core Engine Highlights

* **Logical Grounding via [Queen](https://abhay-ai.github.io/Queen/)**: offloads coordinate verification, pins, checking lines, and discoveries to a symbolic SWI-Prolog rulebase, acting as the LLM's spatial "eyes."
* **Tension-Aware Utility Minimization**: Applies a mathematical `-0.5` penalty to neutral piece exchanges that prematurely resolve board tension, steering the LLM to choose quiet, strategic developing moves instead.
* **Minimax Evasion (Defeatism Blocker)**: If all moves have negative utility, the bot runs minimax simulations on all King escape routes to find the path that maximizes resistance and prolongs the game.
* **Stateful Strategic Memory**: Tracks and adapts a long-term strategic plan across turns, dynamically adjusting to the game phase (Opening, Middlegame, Endgame).
* **Autopsy Replay Dashboard**: Generates comprehensive JSON Lines and CSV logs of the LLM's System 2 thoughts, which can be dragged directly into the interactive [visualizer.html](logs/visualizer.html) dashboard.

---

## 🚀 Quick Setup Overview

### 1. Install Prolog & Dependencies
Ensure you have SWI-Prolog installed on your OS (`sudo apt install swi-prolog` or `sudo dnf install pl`), then run:
```bash
pip install -r requirements.txt
pip install -e ./Queen
```

### 2. Configure Environment Variables
Create a `.env` file at the root of the project:
```ini
LICHESS_API_TOKEN=your_lichess_api_token
LICHESS_MY_USERNAME=your_username
LICHESS_MODEL_NAME=cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit
```

### 3. Spin Up Local vLLM Inference
Gemma 4 AWQ is served locally using vLLM to enable native tool calling and sub-second token latency:
```bash
bash start_vllm.sh
```

### 4. Play and Benchmark
* **Start Lichess Bot**: `python3 lichess_bot.py`
* **Run Puzzles Elo Benchmark**: `python3 test_puzzles.py`
* **Run Pure LLM Baseline**: `python3 test_puzzles_baseline.py`
* **Play Stockfish Locally**: `python3 play_stockfish.py`

For detailed setup commands, environment variables, and troubleshooting guides, view the interactive setup page at [docs/readme.html](docs/readme.html).

---

## ⚖️ License

Distributed under the MIT License. See `LICENSE` for more information.
