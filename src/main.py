"""Chainlit UI for Fix That Prompt game."""

import os

import chainlit as cl
from dotenv import load_dotenv
from loguru import logger

from .components.game import FixThatPromptGame
from .models.player_session import GameRound
from .utils.logger import setup_logging

# Load environment variables
load_dotenv()

# Initialize logging
setup_logging(os.getenv("LOG_LEVEL", "INFO"))

# Initialize game instance
game: FixThatPromptGame | None = None


def initialize_game() -> FixThatPromptGame:
    """Initialize the game instance."""
    global game
    if game is None:
        try:
            game = FixThatPromptGame()
            logger.info("Game initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize game: {e}")
            raise
    return game


@cl.on_chat_start
async def start():
    """Handle chat start - welcome message and username input."""

    # Initialize game
    try:
        initialize_game()
    except Exception as e:
        await cl.Message(
            content=f"❌ **Error initializing game:** {str(e)}\n\n"
            "Please check your configuration and try again.\n\n"
            "💡 **Need help?** Type **'help'** for instructions.\n"
            "🏆 **Want to see the leaderboard?** Type **'leaderboard'**."
        ).send()
        return

    # Welcome message
    welcome_msg = """
# 🎮 Welcome to Fix That Prompt!

**The Ultimate Prompt Engineering Challenge Game!**

## 🎯 How to Play:
1. **Enter a unique username** to start your game
2. **Play up to 3 rounds** - each round presents:
   - A bad prompt and its weak response
   - COSTAR framework guidance
   - Your chance to improve the prompt
3. **Get scored** using RAGAS evaluation (max 10 points)
4. **Climb the leaderboard** with your best score!

## 📊 Scoring Breakdown:
- **Prompt Quality (0-5 points):** Clarity, specificity, completeness
- **COSTAR Usage (0-3 points):** Framework adherence
- **Creativity Bonus (0-2 points):** Innovation and uniqueness

## 🏆 Rules:
- Each username can play only **once**
- You can stop after any round
- Your **best round score** is your final score
- Top 10 players make the leaderboard!

---

**Ready to become a prompt engineering master? Let's start!**
"""

    await cl.Message(content=welcome_msg).send()

    # Initialize user session
    cl.user_session.set("game_state", "waiting_for_username")
    cl.user_session.set("username", None)
    cl.user_session.set("current_round", 0)
    cl.user_session.set("current_bad_prompt", None)

    # Ask for username
    await cl.Message(
        content="👤 **Please enter your unique username to start playing:**"
    ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages based on game state."""

    game_state = cl.user_session.get("game_state", "waiting_for_username")
    username = cl.user_session.get("username")

    if game_state == "waiting_for_username":
        await handle_username_input(message.content)
    elif game_state == "waiting_for_round_decision":
        await handle_round_decision(message.content, username)
    elif game_state == "waiting_for_improved_prompt":
        await handle_improved_prompt(message.content, username)
    elif game_state == "game_ended":
        await handle_post_game(message.content)
    else:
        await cl.Message(
            content="🤔 I'm not sure what to do with that. Try typing 'help' or 'leaderboard'."
        ).send()


async def handle_username_input(username_input: str):
    """Handle username input and start the game."""

    username = username_input.strip()

    # Special commands
    if username.lower() in ["help", "leaderboard", "stats"]:
        await handle_special_commands(username.lower())
        return

    if not username:
        await cl.Message(
            content="❌ **Username cannot be empty.** Please enter a valid username.\n\n"
            "💡 Or type **'help'** for instructions, **'leaderboard'** to see rankings, or **'stats'** for game info."
        ).send()
        return

    # Try to start new game
    success, message, session = await game.start_new_game(username)

    if not success:
        await cl.Message(
            content=f"❌ **{message}**\n\n"
            "Please choose a different username or type 'leaderboard' to see current players:"
        ).send()
        return

    # Successfully started game
    cl.user_session.set("username", username)
    cl.user_session.set("game_state", "waiting_for_round_decision")

    await cl.Message(
        content=f"🎉 **{message}**\n\n"
        "You can play up to **3 rounds**. Your best score will be your final score!\n\n"
        "🚀 **Starting your first round now...**"
    ).send()

    await start_new_round(username)


async def start_new_round(username: str):
    """Start a new round for the player."""

    session = game.get_current_session(username)
    if not session or not session.can_play_more_rounds:
        await end_game(username)
        return

    # Get bad prompt for this round
    bad_prompt = game.get_current_round_prompt(username)
    if not bad_prompt:
        await cl.Message(
            content="❌ **Error getting prompt for this round.** Something went wrong.\n\n"
            "🔄 **Try typing:** **'next'** to try starting a round again\n"
            "🛑 **Or type:** **'stop'** to end your game\n"
            "📊 **Or type:** **'stats'** to see your current progress"
        ).send()
        return

    cl.user_session.set("current_bad_prompt", bad_prompt)

    # Display round information
    round_msg = f"""
## 🎯 Round {session.current_round} of {session.max_rounds}

### 📂 **Category:** {bad_prompt.category}

### 📝 **Context:**
{bad_prompt.context}

### ❌ **Bad Prompt:**
```
{bad_prompt.bad_prompt}
```

### 😬 **Weak Response:**
```
{bad_prompt.weak_response}
```

---

{game.get_costar_guidance()}

---

## 🚀 **Your Turn!**
Now it's time to improve this prompt! Write a better version that addresses the issues above.

**Type your improved prompt below:**
"""

    await cl.Message(content=round_msg).send()
    cl.user_session.set("game_state", "waiting_for_improved_prompt")


async def handle_improved_prompt(improved_prompt: str, username: str):
    """Handle the user's improved prompt submission."""

    if not improved_prompt.strip():
        await cl.Message(
            content="❌ **Your improved prompt cannot be empty.** Please try again.\n\n"
            "💡 **Need help?** Remember to use the COSTAR framework to improve the prompt!\n"
            "🛑 **Want to stop playing?** Type **'stop'** to end your game."
        ).send()
        return

    bad_prompt = cl.user_session.get("current_bad_prompt")
    if not bad_prompt:
        await cl.Message(
            content="❌ **Error: No current prompt found.** Something went wrong.\n\n"
            "🔄 **Try typing:** **'next'** to start a new round\n"
            "🛑 **Or type:** **'stop'** to end your game"
        ).send()
        return

    # Show processing message
    processing_msg = await cl.Message(
        content="⏳ **Processing your improved prompt...**\n\n"
        "🤖 Generating improved response...\n"
        "📊 Evaluating with LLM-as-a-judge...\n"
        "🎯 Calculating scores...\n\n"
        "*This may take a moment...*"
    ).send()

    # Submit the round
    success, message, game_round = await game.submit_round(
        username, bad_prompt, improved_prompt
    )

    # Remove processing message
    await processing_msg.remove()

    if not success:
        await cl.Message(
            content=f"❌ **Error:** {message}\n\n"
            "Please try submitting your improved prompt again.\n\n"
            "💡 **Need help?** Use the COSTAR framework to improve the prompt!\n"
            "🛑 **Want to stop?** Type **'stop'** to end your game."
        ).send()
        return

    # Display results
    await display_round_results(game_round, username)


async def display_round_results(game_round: GameRound, username: str):
    """Display the results of a completed round."""

    session = game.get_current_session(username)

    results_msg = f"""
## 🎉 Round {game_round.round_number} Complete!

### 🔄 **Your Improved Prompt:**
```
{game_round.improved_prompt}
```

### ✨ **Improved Response:**
```
{game_round.improved_response}
```

---

### 📊 **Your Score: {game_round.ragas_score:.1f}/10**

{game_round.feedback}

---

### 📈 **Session Progress:**
- **Current Round:** {session.current_round - 1} of {session.max_rounds} completed
- **Best Score This Game:** {session.best_score:.1f}/10
- **Rounds Remaining:** {session.max_rounds - (session.current_round - 1)}
"""

    await cl.Message(content=results_msg).send()

    # Check if more rounds are available
    if session.can_play_more_rounds:
        await cl.Message(
            content="🎮 **What would you like to do next?**\n\n"
            "Type:\n"
            "- **'next'** to play another round\n"
            "- **'stop'** to end the game now\n"
            "- **'stats'** to see your current stats"
        ).send()
        cl.user_session.set("game_state", "waiting_for_round_decision")
    else:
        await cl.Message(
            content="🎊 **You've completed all 3 rounds!** Let's see your final results..."
        ).send()
        await end_game(username)


async def handle_round_decision(decision: str, username: str):
    """Handle player's decision between rounds."""

    decision = decision.lower().strip()

    if decision in ["next", "continue", "play"]:
        await start_new_round(username)
    elif decision in ["stop", "end", "quit", "finish"]:
        await end_game(username)
    elif decision in ["stats", "status", "summary"]:
        await show_session_stats(username, in_game=True)
    elif decision in ["leaderboard", "board", "rankings"]:
        await show_leaderboard(in_game=True, username=username)
    else:
        await cl.Message(
            content="🤔 **Please choose:**\n\n"
            "- **'next'** to play another round\n"
            "- **'stop'** to end the game\n"
            "- **'stats'** to see your stats\n"
            "- **'leaderboard'** to see rankings"
        ).send()


async def end_game(username: str):
    """End the game and show final results."""

    success, message, final_results = game.end_game(username)

    if not success:
        await cl.Message(
            content=f"❌ **Error ending game:** {message}\n\n"
            "🎮 **Want to start a new game?** Enter a different username!\n"
            "🏆 **Check the leaderboard:** Type **'leaderboard'**\n"
            "💡 **Need help?** Type **'help'** for instructions"
        ).send()
        return

    # Display final results
    final_msg = f"""
# 🏁 Game Complete!

## 🎊 **Final Results for {username}:**

### 🏆 **Final Score: {final_results['final_score']:.1f}/10**
- **Rounds Played:** {final_results['rounds_played']}
- **Best Round Score:** {final_results['best_round_score']:.1f}/10

### 📈 **Leaderboard Position:**
- **Your Rank:** #{final_results['rank']} out of {final_results['total_players']} players
"""

    if final_results["is_top_10"]:
        final_msg += "🎉 **Congratulations! You made it to the Top 10!**\n\n"

    final_msg += "---\n\n### 🏆 **Current Top 10 Leaderboard:**\n\n"

    for i, player in enumerate(final_results["top_players"][:10]):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
        highlight = "**" if player["username"] == username else ""
        final_msg += f"{medal} {highlight}#{i+1} {player['username']} - {player['final_score']:.1f}/10{highlight}\n"

    final_msg += """

---

## 🎮 **Game Stats:**
Thanks for playing **Fix That Prompt!**

🎮 **Want to play again?** Enter a different username to start a new game!

🔄 **Type 'leaderboard'** to see the current rankings anytime.
💡 **Type 'help'** for game instructions.
"""

    await cl.Message(content=final_msg).send()

    cl.user_session.set("game_state", "game_ended")


async def show_session_stats(username: str, in_game: bool = False):
    """Show current session statistics."""

    summary = game.get_session_summary(username)
    if not summary:
        await cl.Message(
            content="❌ **No active session found.**\n\n"
            "🎮 **Ready to start playing?** Enter your unique username!\n"
            "💡 Type **'help'** for instructions or **'leaderboard'** to see rankings."
        ).send()
        return

    # Add game status indicator when viewed during active gameplay
    game_status = ""
    if in_game:
        game_status = "🎮 **YOUR GAME IS STILL ACTIVE** 🎮\n\n"

    stats_msg = f"""
{game_status}## 📊 Session Stats for {username}

### 🎯 **Current Progress:**
- **Round:** {summary['current_round'] - 1} of {summary['max_rounds']} completed
- **Best Score:** {summary['best_score']:.1f}/10
- **Can Play More:** {'Yes' if summary['can_play_more'] else 'No'}

### 📈 **Round History:**
"""

    for round_info in summary["rounds"]:
        stats_msg += f"- **Round {round_info['round_number']}:** {round_info['score']:.1f}/10 ({round_info['category']})\n"

    # Different navigation based on context
    if in_game and summary["can_play_more"]:
        stats_msg += """

---

🚀 **CONTINUE YOUR GAME:**
- Type **'next'** to play your next round
- Type **'stop'** to end your game now
- Type **'leaderboard'** to see current rankings
"""
    elif in_game and not summary["can_play_more"]:
        stats_msg += """

---

🎊 **Game Complete!**
- Type **'stop'** to see your final results
- Type **'leaderboard'** to see current rankings
"""
    else:
        stats_msg += """

---

🎮 **What's next?**
- Type **'next'** to continue playing
- Type **'stop'** to end your game
- Type **'leaderboard'** to see rankings
"""

    await cl.Message(content=stats_msg).send()


async def show_leaderboard(in_game: bool = False, username: str = None):
    """Show the current leaderboard."""

    top_players = game.get_leaderboard(10)

    if not top_players:
        if in_game:
            await cl.Message(
                content="🏆 **Leaderboard is empty!** You could be the first!\n\n"
                "🎮 **YOUR GAME IS STILL ACTIVE** - Type **'next'** to continue playing!\n"
                "🛑 Or type **'stop'** to end your game now."
            ).send()
        else:
            await cl.Message(
                content="🏆 **Leaderboard is empty!** Be the first to play and set a score!\n\n"
                "🎮 **Ready to start?** Enter your unique username to begin playing!\n"
                "💡 Type **'help'** for detailed game instructions."
            ).send()
        return

    # Add game status indicator when viewed during active gameplay
    game_status = ""
    if in_game:
        game_status = "🎮 **YOUR GAME IS STILL ACTIVE** 🎮\n\n"

    leaderboard_msg = f"{game_status}# 🏆 Top 10 Leaderboard\n\n"

    for i, player in enumerate(top_players):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
        highlight = (
            "👈 **YOU**"
            if in_game and username and player["username"].lower() == username.lower()
            else ""
        )
        leaderboard_msg += (
            f"{medal} **#{i+1} {player['username']}** - {player['final_score']:.1f}/10 "
        )
        leaderboard_msg += f"({player['rounds_played']} rounds) {highlight}\n"

    game_stats = game.get_game_stats()
    leaderboard_msg += f"""

---

📊 **Game Statistics:**
- **Total Players:** {game_stats['total_players']}
- **Average Score:** {game_stats['average_score']:.1f}/10
- **Active Players:** {len(game_stats['active_players'])}

---
"""

    # Different navigation based on context
    if in_game:
        session = game.get_current_session(username) if username else None
        if session and session.can_play_more_rounds:
            leaderboard_msg += """
🚀 **CONTINUE YOUR GAME:**
- Type **'next'** to play your next round
- Type **'stop'** to end your game now
- Type **'stats'** to see your current progress
"""
        else:
            leaderboard_msg += """
🎊 **FINISH YOUR GAME:**
- Type **'stop'** to see your final results and ranking
- Type **'stats'** to see your game summary
"""
    else:
        leaderboard_msg += """
🎮 **Ready to play?** Enter your unique username to start your game!
💡 Type **'help'** for detailed game instructions.
"""

    await cl.Message(content=leaderboard_msg).send()


async def handle_special_commands(command: str):
    """Handle special commands like help, leaderboard, stats."""

    if command == "help":
        help_msg = """
# 🎮 Fix That Prompt - Help

## 🎯 **Game Commands:**
- **Username** - Start a new game
- **'next'** - Play another round (during game)
- **'stop'** - End current game
- **'stats'** - Show your session stats
- **'leaderboard'** - Show top 10 players

## 📖 **How Scoring Works:**
- **Prompt Quality (0-5):** Clarity and completeness
- **COSTAR Usage (0-3):** Framework adherence
- **Creativity (0-2):** Innovation bonus
- **Total:** Up to 10 points per round

## 🏆 **Game Rules:**
- Each username plays only once
- Up to 3 rounds per game
- Best round score = final score
- Stop anytime after any round

**Ready to play? Enter your username!**
"""
        await cl.Message(content=help_msg).send()

    elif command == "leaderboard":
        await show_leaderboard()

    elif command == "stats":
        game_stats = game.get_game_stats()
        stats_msg = f"""
# 📊 Game Statistics

- **Total Prompts Available:** {game_stats['total_prompts_available']}
- **Prompt Categories:** {len(game_stats['prompt_categories'])}
- **Total Players:** {game_stats['total_players']}
- **Average Score:** {game_stats['average_score']:.1f}/10
- **Currently Active:** {game_stats['active_sessions']} players

**Categories Available:**
{', '.join(game_stats['prompt_categories'])}

**Enter your username to start playing!**
"""
        await cl.Message(content=stats_msg).send()


async def handle_post_game(message_content: str):
    """Handle messages after game has ended."""

    content = message_content.lower().strip()

    if content in ["leaderboard", "board", "rankings"]:
        await show_leaderboard()
    elif content in ["help", "info"]:
        await cl.Message(
            content="🎮 **Game ended!** To play again, enter a different username.\n\n"
            "Type 'leaderboard' to see current rankings."
        ).send()
    elif content in ["stats"]:
        await handle_special_commands("stats")
    else:
        # Check if this could be a new username attempt
        username = message_content.strip()
        if (
            username
            and len(username) > 0
            and username.lower()
            not in ["leaderboard", "board", "rankings", "help", "info", "stats"]
        ):
            # Reset game state to allow new game
            cl.user_session.set("game_state", "waiting_for_username")
            cl.user_session.set("username", None)
            cl.user_session.set("current_round", 0)
            cl.user_session.set("current_bad_prompt", None)

            # Handle as new username input
            await handle_username_input(username)
        else:
            await cl.Message(
                content="🏁 **Your game has ended!** \n\n"
                "🎮 **Ready for another game?** Enter a different username to start!\n"
                "🏆 Type **'leaderboard'** to see current rankings.\n"
                "💡 Type **'help'** for game instructions."
            ).send()


if __name__ == "__main__":
    # This won't be called when running with chainlit run
    # but can be useful for testing
    logger.info("Starting Fix That Prompt game...")
