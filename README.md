# 🎮 Fix That Prompt!

An interactive game that challenges players to improve bad prompts using AI-powered evaluation and the COSTAR framework.

## 🎯 What is Fix That Prompt?

**Fix That Prompt!** is a single-player game where multiple users take turns to improve bad prompts and compete for the highest RAGAS-based scores. Each player can play only once with a unique username, making every attempt count!

### 🧩 How the Game Works

1. **Enter a unique username** to start your game session
2. **Play up to 3 rounds** - each presenting:
   - A bad prompt with weak response
   - COSTAR framework guidance
   - Your chance to rewrite and improve the prompt
3. **Get scored** using LLM-as-a-judge evaluation (max 10 points)
4. **Compete** for a spot on the Top 10 leaderboard!

### 📊 Scoring System

- **Prompt Quality (0-5 points):** Clarity, specificity, and completeness
- **COSTAR Usage (0-3 points):** Adherence to the COSTAR framework
- **Creativity Bonus (0-2 points):** Innovation and unique approaches
- **Total:** Up to 10 points per round
- **Final Score:** Your best round score becomes your leaderboard score

### 🎮 Game Features

#### Core Functionality
- ✅ Unique username enforcement
- ✅ Multi-round gameplay (up to 3 rounds)
- ✅ COSTAR framework guidance
- ✅ Real-time LLM-as-a-judge evaluation
- ✅ Interactive leaderboard
- ✅ Session persistence
- ✅ Comprehensive logging

#### Scoring & Evaluation
- ✅ Multi-criteria evaluation (Quality + COSTAR + Creativity)
- ✅ Detailed feedback for each submission
- ✅ Encouraging performance messages
- ✅ Best-score-wins final scoring

#### User Experience
- ✅ Intuitive Chainlit chat interface
- ✅ Clear game instructions and guidance
- ✅ Real-time feedback and scoring
- ✅ Top 10 leaderboard with rankings
- ✅ Session statistics and progress tracking

### 🏗️ Architecture

The game is built with robust architecture following SOLID principles:

```
fix-that-prompt/
├── data/                     # Game data and persistence
│   ├── bad_prompts.json     # Prompt scenarios
│   └── leaderboard.json     # Player scores (auto-created)
├── src/                     # Source code
│   ├── components/          # Game logic and session management
│   ├── database/           # Data persistence layer
│   ├── evaluators/         # RAGAS scoring system
│   ├── models/            # Data models and structures
│   ├── prompts/           # Prompt loading utilities
│   └── utils/             # Logging and utilities
├── logs/                   # Application logs (auto-created)
├── main.py                # Application entry point
└── pyproject.toml         # Project configuration
```

### 🛠️ Tech Stack

- **UI Framework:** [Chainlit](https://docs.chainlit.io/) - Interactive chat interface
- **LLM Pipeline:** [LangChain](https://python.langchain.com/) - AI orchestration
- **Evaluation:** Custom LLM-as-a-judge scoring system
- **Logging:** [Loguru](https://loguru.readthedocs.io/) - Comprehensive logging
- **Data Storage:** DynamoDB (AWS) with JSON fallback (local development)