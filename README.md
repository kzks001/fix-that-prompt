# 🎮 Fix That Prompt!

A production-grade interactive game that challenges players to improve bad prompts using AI-powered evaluation and the COSTAR framework.

## 🧩 Game Overview

**Fix That Prompt!** is a single-player game where multiple users take turns to improve bad prompts and compete for the highest RAGAS-based scores. Each player can play only once with a unique username, making every attempt count!

### 🎯 How It Works

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

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- OpenAI API key
- uv (recommended) or pip

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd fix-that-prompt
   ```

2. **Install dependencies:**
   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -r requirements.txt
   ```

3. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

4. **Run the game:**
   ```bash
   # Using uv
   uv run chainlit run main.py

   # Or with activated virtual environment
   chainlit run main.py
   ```

5. **Open your browser** and navigate to `http://localhost:8000`

## 🏗️ Architecture

The game is built with production-grade architecture following SOLID principles:

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
- **Data Storage:** JSON files (easily migrateable to databases)

## 🎮 Game Features

### Core Functionality
- ✅ Unique username enforcement
- ✅ Multi-round gameplay (up to 3 rounds)
- ✅ COSTAR framework guidance
- ✅ Real-time LLM-as-a-judge evaluation
- ✅ Interactive leaderboard
- ✅ Session persistence
- ✅ Comprehensive logging

### Scoring & Evaluation
- ✅ Multi-criteria evaluation (Quality + COSTAR + Creativity)
- ✅ Detailed feedback for each submission
- ✅ Encouraging performance messages
- ✅ Best-score-wins final scoring

### User Experience
- ✅ Intuitive Chainlit chat interface
- ✅ Clear game instructions and guidance
- ✅ Real-time feedback and scoring
- ✅ Top 10 leaderboard with rankings
- ✅ Session statistics and progress tracking

## 🔧 Configuration

### Environment Variables

Create a `.env` file with:

```env
OPENAI_API_KEY=your_openai_api_key_here
LOG_LEVEL=INFO
```

### Game Configuration

Key settings can be modified in the source code:

- **Model:** Change `model_name` in `FixThatPromptGame` initialization
- **Max Rounds:** Modify `max_rounds` in `PlayerSession`
- **Scoring Weights:** Adjust criteria in `RAGASPromptEvaluator`
- **Prompts:** Add more scenarios to `data/bad_prompts.json`

## 📈 Production Deployment

The codebase is designed for easy deployment with minimal changes:

### Docker Deployment (Future)
```dockerfile
# Dockerfile structure ready for:
# - Multi-stage builds
# - Environment variable injection
# - Volume mounting for data persistence
# - Health checks
```

### AWS Deployment (Future)
- **ECS/Fargate:** Container orchestration
- **RDS/DocumentDB:** Database migration
- **CloudWatch:** Enhanced logging
- **Load Balancer:** High availability

## 🔍 Monitoring & Logging

Comprehensive logging is built-in:

- **Game Events:** Player actions, rounds, scores
- **Application Logs:** System events and errors
- **Performance:** Response times and evaluations
- **File Rotation:** Automatic log management

Log files are created in the `logs/` directory:
- `fix_that_prompt.log` - General application logs
- `game_events.log` - Game-specific events
- `errors.log` - Error tracking

## 🧪 Development

### Code Quality
- **Formatting:** Ruff with 80-character lines
- **Documentation:** Google-style docstrings
- **Architecture:** SOLID principles with OOP
- **Type Hints:** Full type annotation

### Running in Development
```bash
# Install development dependencies
uv sync --group dev

# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Run with debug logging
LOG_LEVEL=DEBUG uv run chainlit run main.py
```

## 📊 Game Statistics

The game tracks comprehensive statistics:
- Total players and average scores
- Category distribution of prompts
- Session completion rates
- Performance metrics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the coding standards (ruff formatting)
4. Add comprehensive logging
5. Test thoroughly
6. Submit a pull request

## 📋 TODO / Roadmap

- [ ] Docker containerization
- [ ] Database migration (PostgreSQL/MongoDB)
- [ ] Admin dashboard
- [ ] Advanced analytics
- [ ] Multi-language support
- [ ] Custom prompt categories
- [ ] Team/multiplayer modes

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **COSTAR Framework** - For prompt engineering methodology
- **OpenAI GPT Models** - For LLM-as-a-judge evaluation
- **Chainlit** - For the excellent chat UI framework
- **LangChain** - For LLM orchestration

---

**Ready to become a prompt engineering master? Start playing Fix That Prompt today! 🚀**
