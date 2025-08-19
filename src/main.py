"""Chainlit UI for Fix That Prompt game."""

import asyncio
import os

import chainlit as cl
from chainlit import Action
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


# Action handlers for buttons
@cl.action_callback("help")
async def help_action(action):
    """Handle help button clicks."""

    help_msg = """
# 🎮 Fix That Prompt - Game Guide

## 🎯 **How It Works:**
Each round, you receive a **poorly written prompt** with its **weak AI response**. Your job is to **improve the prompt** using the **COSTAR framework** to generate a better response. The more improvement you achieve, the higher your score!

## 🚀 **What Happens When You Start:**
1. **You'll see a bad prompt** with its weak response
2. **Analyze what's wrong** with the original prompt
3. **Write a better prompt** using the COSTAR framework
4. **Type it in the chat box** and press Enter
5. **See your improved response** and get scored!

## 🔧 **COSTAR Framework - Use These Elements:**

**C - Context:** Provide clear context and background information
**O - Objective:** Define specific, measurable objectives  
**S - Style:** Specify the desired tone, format, and style
**T - Tone:** Set the appropriate conversational tone
**A - Audience:** Identify the target audience clearly
**R - Response:** Specify the desired response format and structure

## 📊 **Detailed Scoring:**
- **Prompt Quality (0-5 points):** Clarity, specificity, completeness
- **COSTAR Usage (0-3 points):** Framework adherence
- **Creativity Bonus (0-2 points):** Innovation and uniqueness
- **Maximum:** 10 points per round

## 🏆 **Game Rules:**
- Each username can play only **once**
- Up to **3 rounds** per game
- You can **stop after any round**
- Your **best round score** becomes your final score
- Top 10 players make the **leaderboard**

**Use the buttons below to navigate through the game!**
"""

    # Build actions list - only show Top Prompt if user has completed all rounds
    actions = [
        Action(
            name="back_to_menu",
            payload={"action": "back_to_menu"},
            label="🏠 Back to Menu",
        ),
        Action(
            name="leaderboard",
            payload={"action": "leaderboard"},
            label="🏆 Leaderboard",
        ),
        Action(name="stats", payload={"action": "stats"}, label="📊 Statistics"),
    ]

    # Check if current user has completed all rounds
    username = cl.user_session.get("username")
    if username:
        player_data = cl.user_session.get("player_data")
        if player_data and not player_data.can_play_more_rounds:
            actions.append(
                Action(
                    name="top_leaderboard_prompt",
                    payload={"action": "top_leaderboard_prompt"},
                    label="🎯 Top Prompt",
                )
            )

    new_message = await cl.Message(
        content=help_msg,
        actions=actions,
    ).send()

    cl.user_session.set("main_message", new_message)


@cl.action_callback("leaderboard")
async def leaderboard_action(action):
    """Handle leaderboard button clicks."""

    top_players = game.get_leaderboard(10)

    if not top_players:
        leaderboard_msg = """
# 🏆 Leaderboard

**No players yet!** Be the first to set a score and make your mark on the leaderboard.

🎮 **Ready to play?** Use the buttons below to navigate!
"""
        new_message = await cl.Message(
            content=leaderboard_msg,
            actions=[
                Action(
                    name="back_to_menu",
                    payload={"action": "back_to_menu"},
                    label="🏠 Back to Menu",
                ),
                Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 Statistics"
                ),
            ],
        ).send()

        cl.user_session.set("main_message", new_message)
    else:
        game_status = ""
        game_state = cl.user_session.get("game_state", "main_menu")
        username = cl.user_session.get("username")
        if game_state == "waiting_for_round_decision" and username:
            game_status = "🎮 **YOUR GAME IS STILL ACTIVE** 🎮\n\n"

        leaderboard_msg = f"""
# 🏆 Top 10 Leaderboard

{game_status}"""

        for i, player in enumerate(top_players, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            leaderboard_msg += f"{emoji} **{player['username']}** - {player['final_score']:.1f}/10 ({player['rounds_played']} rounds)\n"

        game_stats = game.get_game_stats()
        leaderboard_msg += f"""

## 📊 Game Statistics:
- **Total Players:** {game_stats['total_players']}
- **Average Score:** {game_stats['average_score']:.1f}/10
- **Active Players:** {len(game_stats['active_players'])}

🎮 **Ready to continue?** Click the 'Back to Menu' button to return to your game!
"""

        # Build actions list - only show Top Prompt if user has completed all rounds
        actions = [
            Action(
                name="back_to_menu",
                payload={"action": "back_to_menu"},
                label="🏠 Back to Menu",
            ),
            Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
            Action(name="stats", payload={"action": "stats"}, label="📊 Statistics"),
        ]

        # Check if current user has completed all rounds
        username = cl.user_session.get("username")
        if username:
            player_data = cl.user_session.get("player_data")
            if player_data and not player_data.can_play_more_rounds:
                actions.append(
                    Action(
                        name="top_leaderboard_prompt",
                        payload={"action": "top_leaderboard_prompt"},
                        label="🎯 Top Prompt",
                    )
                )

        new_message = await cl.Message(
            content=leaderboard_msg,
            actions=actions,
        ).send()

        cl.user_session.set("main_message", new_message)


@cl.action_callback("stats")
async def stats_action(action):
    """Handle stats button clicks."""

    game_stats = game.get_game_stats()
    stats_msg = f"""
# 📊 Game Statistics

## 🎮 **Overall Stats:**
- **Prompt Categories:** {len(game_stats['prompt_categories'])}
- **Total Players:** {game_stats['total_players']}
- **Average Score:** {game_stats['average_score']:.1f}/10
- **Currently Active:** {game_stats['active_sessions']} players

**Categories Available:**
{', '.join(game_stats['prompt_categories'])}

**Ready to continue? Click the 'Back to Menu' button to return to your game!**
"""

    # Build actions list - only show Top Prompt if user has completed all rounds
    actions = [
        Action(
            name="back_to_menu",
            payload={"action": "back_to_menu"},
            label="🏠 Back to Menu",
        ),
        Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
        Action(
            name="leaderboard",
            payload={"action": "leaderboard"},
            label="🏆 Leaderboard",
        ),
    ]

    # Check if current user has completed all rounds
    username = cl.user_session.get("username")
    if username:
        player_data = cl.user_session.get("player_data")
        if player_data and not player_data.can_play_more_rounds:
            actions.append(
                Action(
                    name="top_leaderboard_prompt",
                    payload={"action": "top_leaderboard_prompt"},
                    label="🎯 Top Prompt",
                )
            )

    new_message = await cl.Message(
        content=stats_msg,
        actions=actions,
    ).send()

    cl.user_session.set("main_message", new_message)


async def show_authentication_prompt():
    """Show the authentication prompt screen."""
    main_message = await cl.Message(
        content="""
# 🎮 **Welcome to Fix That Prompt!**
*Transform bad prompts into brilliant ones using AI and the COSTAR framework*

## 🎯 **What You'll Do:**
- **See bad prompts** with weak AI responses
- **Write better prompts** using the COSTAR framework
- **Get scored** on how much you improve them
- **Compete** on the leaderboard!

👤 **Enter your Singlife email:**

💡 *eg. sk01@singlife.com*
"""
    ).send()

    cl.user_session.set("main_message", main_message)


@cl.action_callback("next")
async def next_action(action):
    """Handle next round button clicks."""

    username = cl.user_session.get("username")
    player_data = cl.user_session.get("player_data")

    if username and player_data:
        # Refresh player data from database to ensure we have the latest state
        updated_player_data = game.leaderboard_db.get_player_history(username)
        cl.user_session.set("player_data", updated_player_data)

        if updated_player_data and updated_player_data.can_play_more_rounds:
            await start_new_round(username)
        else:
            await show_completed_user_menu(updated_player_data)


@cl.action_callback("stop")
async def stop_action(action):
    """Handle stop game button clicks."""

    username = cl.user_session.get("username")
    player_data = cl.user_session.get("player_data")

    if username and player_data:
        # Refresh player data from database
        updated_player_data = game.leaderboard_db.get_player_history(username)
        cl.user_session.set("player_data", updated_player_data)

        if updated_player_data:
            if (
                updated_player_data.is_completed
                or updated_player_data.rounds_played == 0
            ):
                # Show completed menu or back to main menu if no rounds played
                if updated_player_data.rounds_played > 0:
                    await show_completed_user_menu(updated_player_data)
                else:
                    await show_active_user_menu(updated_player_data)
            else:
                # Show in-progress menu
                await show_active_user_menu(updated_player_data)


@cl.action_callback("back_to_menu")
async def back_to_menu_action(action):
    """Handle back to menu button clicks - shows appropriate menu based on user status."""

    username = cl.user_session.get("username")

    if not username:
        # No username in session, restart the app
        username_message = await cl.Message(
            content="👤 **Enter your SingLife email:**\n\n💡 *eg. sk01@singlife.com*"
        ).send()
        cl.user_session.set("main_message", username_message)
        cl.user_session.set("game_state", "waiting_for_username")
        return

    # Get player data and show appropriate menu
    player_data = game.leaderboard_db.get_player_history(username)
    if not player_data:
        # User doesn't exist, create them
        player_data = game.leaderboard_db.get_or_create_player(username)

    # Update session with latest data
    cl.user_session.set("player_data", player_data)

    # Show appropriate menu based on completion status
    if player_data.is_completed:
        await show_completed_user_menu(player_data)
    else:
        await show_active_user_menu(player_data)


@cl.action_callback("play_round")
async def play_round_action(action):
    """Handle play round button clicks."""

    username = cl.user_session.get("username")
    player_data = cl.user_session.get("player_data")

    if not username or not player_data:
        error_message = await cl.Message(
            content="❌ **Error:** Session expired. Please refresh your browser page (F5 or Ctrl+R) to start over.",
        ).send()
        cl.user_session.set("main_message", error_message)
        return

    if not player_data.can_play_more_rounds:
        error_message = await cl.Message(
            content="❌ **You have no rounds remaining!** You've completed all 3 rounds."
        ).send()
        cl.user_session.set("main_message", error_message)
        return

    # Start the round
    await start_new_round(username)


@cl.action_callback("user_history")
async def user_history_action(action):
    """Handle user history button clicks."""

    username = cl.user_session.get("username")
    if not username:
        error_message = await cl.Message(
            content="❌ **Error:** No user session found. Please start a new game first.",
            actions=[
                Action(
                    name="back_to_menu",
                    payload={"action": "back_to_menu"},
                    label="🏠 Back to Menu",
                ),
                Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 Statistics"
                ),
            ],
        ).send()
        cl.user_session.set("main_message", error_message)
        return

    # Get user's game session data (active or completed)
    session = game.get_session_for_history(username)
    if not session or not session.rounds:
        no_history_message = await cl.Message(
            content=f"📜 **No game history found for {username}.**\n\nStart playing to build your history!",
            actions=[
                Action(
                    name="back_to_menu",
                    payload={"action": "back_to_menu"},
                    label="🏠 Back to Menu",
                ),
                Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 Statistics"
                ),
            ],
        ).send()
        cl.user_session.set("main_message", no_history_message)
        return

    history_msg = f"""
# 📜 **Game History for {username}**

## 🎮 **Game Summary:**
- **Total Rounds Played:** {len(session.rounds)}
- **Final Score:** {session.best_score:.1f}/10
- **Game Status:** {"Completed" if not session.can_play_more_rounds else "In Progress"}

---
"""

    for round_data in session.rounds:
        history_msg += f"""
## 🔄 **Round {round_data.round_number}**

### 📝 **Original Bad Prompt:**
```
{round_data.bad_prompt.bad_prompt}
```

### 💬 **Weak Response:**
```
{round_data.bad_prompt.weak_response}
```

### ✨ **Your Improved Prompt:**
```
{round_data.improved_prompt}
```

### 🎯 **Improved Response:**
```
{round_data.improved_response}
```

### 📊 **Score: {round_data.ragas_score:.1f}/10**
{round_data.feedback}

---
"""

    # Build actions list - only show Top Prompt if user has completed all rounds
    actions = [
        Action(
            name="back_to_menu",
            payload={"action": "back_to_menu"},
            label="🏠 Back to Menu",
        ),
        Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
        Action(
            name="leaderboard",
            payload={"action": "leaderboard"},
            label="🏆 Leaderboard",
        ),
        Action(name="stats", payload={"action": "stats"}, label="📊 Statistics"),
    ]

    # Only show Top Prompt button if user has completed all rounds
    if not session.can_play_more_rounds:
        actions.append(
            Action(
                name="top_leaderboard_prompt",
                payload={"action": "top_leaderboard_prompt"},
                label="🎯 Top Prompt",
            )
        )

    history_message = await cl.Message(
        content=history_msg,
        actions=actions,
    ).send()
    cl.user_session.set("main_message", history_message)


@cl.action_callback("top_leaderboard_prompt")
async def top_leaderboard_prompt_action(action):
    """Handle top leaderboard prompt button clicks."""

    top_players = game.get_leaderboard(1)

    if not top_players:
        no_players_message = await cl.Message(
            content="🏆 **No players on the leaderboard yet!**\n\nBe the first to play and claim the top spot!",
            actions=[
                Action(
                    name="back_to_menu",
                    payload={"action": "back_to_menu"},
                    label="🏠 Back to Menu",
                ),
                Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 Statistics"
                ),
            ],
        ).send()
        cl.user_session.set("main_message", no_players_message)
        return

    top_player = top_players[0]
    top_username = top_player["username"]

    # Get the top player's session data (active or completed)
    top_session = game.get_session_for_history(top_username)
    if not top_session or not top_session.rounds:
        error_message = await cl.Message(
            content=f"❌ **Error:** Could not retrieve game data for top player {top_username}.",
            actions=[
                Action(
                    name="back_to_menu",
                    payload={"action": "back_to_menu"},
                    label="🏠 Back to Menu",
                ),
                Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 Statistics"
                ),
            ],
        ).send()
        cl.user_session.set("main_message", error_message)
        return

    # Find their best round (highest scoring round)
    best_round = max(top_session.rounds, key=lambda r: r.ragas_score)

    top_prompt_msg = f"""
# 🎯 **Top Leaderboard Prompt**

## 🏆 **#{1} {top_username} - {top_player['final_score']:.1f}/10**

### 🌟 **Best Round: #{best_round.round_number}**
**Score: {best_round.ragas_score:.1f}/10**

---

### 📝 **Original Bad Prompt:**
```
{best_round.bad_prompt.bad_prompt}
```

### 💬 **Original Weak Response:**
```
{best_round.bad_prompt.weak_response}
```

### ✨ **Top Player's Improved Prompt:**
```
{best_round.improved_prompt}
```

### 🎯 **Resulting Improved Response:**
```
{best_round.improved_response}
```

### 📊 **Evaluation Feedback:**
{best_round.feedback}

---

💡 **Learn from the best!** Study how the top player structured their prompt using the COSTAR framework.
"""

    top_prompt_message = await cl.Message(
        content=top_prompt_msg,
        actions=[
            Action(
                name="back_to_menu",
                payload={"action": "back_to_menu"},
                label="🏠 Back to Menu",
            ),
            Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
            Action(
                name="leaderboard",
                payload={"action": "leaderboard"},
                label="🏆 Leaderboard",
            ),
            Action(name="stats", payload={"action": "stats"}, label="📊 Statistics"),
        ],
    ).send()
    cl.user_session.set("main_message", top_prompt_message)


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


async def authenticate_user() -> tuple[bool, str | None, str | None]:
    """
    Authenticate user using fallback to username input.

    Returns:
        Tuple of (is_authenticated, username, error_message)
    """
    # No authentication configured, use fallback mode
    return False, None, None


@cl.on_chat_start
async def start():
    """Initialize the game and handle authentication."""

    # Initialize game
    try:
        initialize_game()
    except Exception as e:
        await cl.Message(
            content=f"❌ **Error initializing game:** {str(e)}\n\n"
            "Please check your configuration and try again."
        ).send()
        return

    # Try to authenticate user
    is_authenticated, username, auth_error = await authenticate_user()

    if is_authenticated and username:
        # User is authenticated, proceed to game
        player_data = game.leaderboard_db.get_or_create_player(username)
        cl.user_session.set("username", username)
        cl.user_session.set("player_data", player_data)
        cl.user_session.set("game_state", "main_menu")

        # Show the appropriate menu
        if player_data.is_completed:
            await show_completed_user_menu(player_data)
        else:
            await show_active_user_menu(player_data)

    elif auth_error:
        # Authentication failed with error
        await cl.Message(
            content=f"❌ **Authentication Error:** {auth_error}\n\n"
            "Please try authenticating again."
        ).send()
        cl.user_session.set("game_state", "waiting_for_auth")
        await show_authentication_prompt()

    else:
        # No authentication, show prompt
        cl.user_session.set("game_state", "waiting_for_auth")
        cl.user_session.set("username", None)
        cl.user_session.set("player_data", None)
        await show_authentication_prompt()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages based on game state."""

    game_state = cl.user_session.get("game_state", "main_menu")
    username = cl.user_session.get("username")

    if game_state == "main_menu":
        await handle_main_menu_input(message.content)
    elif game_state == "waiting_for_auth":
        await handle_auth_input(message.content)
    elif game_state == "waiting_for_username":
        await handle_username_input(message.content)
    elif game_state == "waiting_for_round_decision":
        await handle_round_decision(message.content, username)
    elif game_state == "waiting_for_improved_prompt":
        await handle_improved_prompt(message.content, username)
    elif game_state == "game_ended":
        await handle_post_game(message.content)
    else:
        # Build actions list - only show Top Prompt if user has completed all rounds
        actions = [
            Action(
                name="back_to_menu",
                payload={"action": "back_to_menu"},
                label="🏠 Back to Menu",
            ),
            Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
            Action(
                name="leaderboard",
                payload={"action": "leaderboard"},
                label="🏆 Leaderboard",
            ),
            Action(name="stats", payload={"action": "stats"}, label="📊 Statistics"),
        ]

        # Check if current user has completed all rounds
        username = cl.user_session.get("username")
        if username:
            player_data = cl.user_session.get("player_data")
            if player_data and not player_data.can_play_more_rounds:
                actions.append(
                    Action(
                        name="top_leaderboard_prompt",
                        payload={"action": "top_leaderboard_prompt"},
                        label="🎯 Top Prompt",
                    )
                )

        await cl.Message(
            content="🤔 I'm not sure what to do with that. Please use the buttons below to navigate.",
            actions=actions,
        ).send()


async def handle_main_menu_input(message_content: str):
    """Handle input from the main menu - only accepts special commands."""

    content = message_content.lower().strip()
    main_message = cl.user_session.get("main_message")

    if not main_message:
        return

    # Handle special commands by triggering the appropriate action
    if content in ["help", "info"]:
        await help_action(None)
    elif content in ["leaderboard", "board", "rankings"]:
        await leaderboard_action(None)
    elif content in ["stats", "statistics"]:
        await stats_action(None)
    else:
        # For any other input, show main menu options
        await main_message.remove()

        # Build actions list - only show Top Prompt if user has completed all rounds
        actions = [
            Action(
                name="back_to_menu",
                payload={"action": "back_to_menu"},
                label="🏠 Back to Menu",
            ),
            Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
            Action(
                name="leaderboard",
                payload={"action": "leaderboard"},
                label="🏆 Leaderboard",
            ),
            Action(name="stats", payload={"action": "stats"}, label="📊 Statistics"),
        ]

        # Check if current user has completed all rounds
        username = cl.user_session.get("username")
        if username:
            player_data = cl.user_session.get("player_data")
            if player_data and not player_data.can_play_more_rounds:
                actions.append(
                    Action(
                        name="top_leaderboard_prompt",
                        payload={"action": "top_leaderboard_prompt"},
                        label="🎯 Top Prompt",
                    )
                )

        new_message = await cl.Message(
            content="""🎮 **Please use the navigation buttons below:**""",
            actions=actions,
        ).send()

        cl.user_session.set("main_message", new_message)


async def handle_auth_input(message_content: str):
    """Handle input during authentication state."""
    content = message_content.lower().strip()

    # Fallback to username input
    await handle_username_input(message_content)


def extract_singlife_username(email: str) -> str | None:
    """Extract username from Singlife email."""
    if not email:
        return None
    email = email.strip().lower()
    if email.endswith("@singlife.com"):
        return email.split("@", 1)[0]
    return None


async def handle_username_input(username_input: str):
    """Handle username input and show appropriate menu based on user status."""

    username_input = username_input.strip()

    if not username_input:
        # Show error message using main_message logic
        main_message = cl.user_session.get("main_message")
        if main_message:
            await main_message.update(
                content="❌ **Email cannot be empty.** Please enter a valid Singlife email address.\n\n💡 *eg. sk01@singlife.com*"
            )
        else:
            new_message = await cl.Message(
                content="❌ **Email cannot be empty.** Please enter a valid Singlife email address.\n\n💡 *eg. sk01@singlife.com*"
            ).send()
            cl.user_session.set("main_message", new_message)

        return

    # Only allow @singlife.com emails
    if "@singlife.com" not in username_input.lower():
        await cl.Message(
            content="❌ **Invalid email domain.** Please enter a valid SingLife email address (@singlife.com).\n\n💡 *eg. sk01@singlife.com*"
        ).send()
        return

    # Extract username from @singlife.com email
    username = extract_singlife_username(username_input)
    if not username:
        await cl.Message(
            content="❌ **Invalid email format.** Please enter a valid SingLife email address.\n\n💡 *eg. sk01@singlife.com*"
        ).send()
        return

    # Get or create user in database
    player_data = game.leaderboard_db.get_or_create_player(username)

    # Store user data in session
    cl.user_session.set("username", username)
    cl.user_session.set("player_data", player_data)
    cl.user_session.set("game_state", "main_menu")

    # Clear the main_message if exists
    main_message = cl.user_session.get("main_message")
    if main_message:
        try:
            await main_message.remove()
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.warning(f"Could not remove main message: {e}")

    # Show the appropriate menu
    if player_data.is_completed:
        await show_completed_user_menu(player_data)
    else:
        await show_active_user_menu(player_data)


async def show_active_user_menu(player_data):
    """Show menu for users who can still play rounds."""

    if player_data.rounds_played == 0:
        # New user
        status_msg = f"""
# 🎮 **Welcome {player_data.username}!**

**You're ready to start your prompt engineering challenge!**

## 🎯 **How It Works:**
- You'll get **3 rounds** to show your prompt improvement skills
- Each round: Fix a bad prompt using the **COSTAR framework**
- Your **best round score** becomes your final leaderboard score
- You can stop after any round or play all 3

## 🚀 **What You'll Do:**
1. **See a bad prompt** with its weak AI response
2. **Write a better prompt** using the COSTAR framework
3. **Type it in the chat** and see your improved response
4. **Get scored** on how much you improved it!

## 📊 **Your Status:**
- **Rounds Remaining:** {player_data.rounds_remaining}/3
- **Current Best Score:** {player_data.final_score:.1f}/10

Ready to become a prompt master?
"""

        actions = [
            Action(
                name="play_round",
                payload={"action": "play_round"},
                label="🚀 Start Round 1",
            ),
            Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
            Action(
                name="leaderboard",
                payload={"action": "leaderboard"},
                label="🏆 Leaderboard",
            ),
            Action(name="stats", payload={"action": "stats"}, label="📊 Statistics"),
        ]
    else:
        # Returning user with some progress
        status_msg = f"""
# 🎮 **Welcome back {player_data.username}!**

**Your Progress So Far:**

## 📊 **Current Stats:**
- **Rounds Played:** {player_data.rounds_played}/3
- **Rounds Remaining:** {player_data.rounds_remaining}
- **Current Best Score:** {player_data.final_score:.1f}/10
- **Last Played:** {player_data.last_played.strftime('%Y-%m-%d %H:%M')}

## 🎯 **What's Next:**
{f"Continue with Round {player_data.rounds_played + 1}!" if player_data.can_play_more_rounds else "You've used all your rounds!"}

Ready to continue your prompt engineering journey?
"""

        if player_data.can_play_more_rounds:
            actions = [
                Action(
                    name="play_round",
                    payload={"action": "play_round"},
                    label=f"🚀 Play Round {player_data.rounds_played + 1}",
                ),
                Action(
                    name="user_history",
                    payload={"action": "user_history"},
                    label="📜 My History",
                ),
                Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 Statistics"
                ),
            ]
        else:
            # This shouldn't happen as completed users go to the other menu, but just in case
            actions = [
                Action(
                    name="user_history",
                    payload={"action": "user_history"},
                    label="📜 My History",
                ),
                Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 Statistics"
                ),
            ]

    main_message = await cl.Message(content=status_msg, actions=actions).send()
    cl.user_session.set("main_message", main_message)


async def show_completed_user_menu(player_data):
    """Show menu for users who have completed all 3 rounds."""

    # Get their rank
    top_players = game.get_leaderboard(50)  # Get enough to find their rank
    rank = "Not found"
    for i, player in enumerate(top_players):
        if player["username"].lower() == player_data.username.lower():
            rank = f"#{i+1}"
            break

    status_msg = f"""
# 🏆 **Welcome back {player_data.username}!**

**You've completed your prompt engineering challenge!**

## 📊 **Your Final Results:**
- **Rounds Played:** {player_data.rounds_played}/3 ✅
- **Final Score:** {player_data.final_score:.1f}/10
- **Leaderboard Rank:** {rank}
- **Completed:** {player_data.last_played.strftime('%Y-%m-%d %H:%M')}

## 🎯 **Explore & Learn:**
Since you've used all your rounds, explore the leaderboard and learn from top performers!

Thanks for playing **Fix That Prompt!**
"""

    actions = [
        Action(
            name="user_history",
            payload={"action": "user_history"},
            label="📜 My History",
        ),
        Action(name="help", payload={"action": "help"}, label="📖 Game Guide"),
        Action(
            name="leaderboard",
            payload={"action": "leaderboard"},
            label="🏆 Leaderboard",
        ),
        Action(name="stats", payload={"action": "stats"}, label="📊 Statistics"),
        Action(
            name="top_leaderboard_prompt",
            payload={"action": "top_leaderboard_prompt"},
            label="🎯 Top Prompt",
        ),
    ]

    main_message = await cl.Message(content=status_msg, actions=actions).send()
    cl.user_session.set("main_message", main_message)


async def start_new_round(username: str):
    """Start a new round for the player."""

    player_data = cl.user_session.get("player_data")
    if not player_data or not player_data.can_play_more_rounds:
        await show_completed_user_menu(player_data)
        return

    # Get a random bad prompt for this round
    bad_prompt = game.prompt_loader.get_random_prompt()
    if not bad_prompt:
        error_message = await cl.Message(
            content="❌ **Error getting prompt for this round.** Something went wrong.",
            actions=[
                Action(name="next", payload={"action": "next"}, label="🔄 Try Again"),
                Action(name="stop", payload={"action": "stop"}, label="🛑 Stop Game"),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 View Stats"
                ),
            ],
        ).send()
        cl.user_session.set("main_message", error_message)
        return

    cl.user_session.set("current_bad_prompt", bad_prompt)

    # Display round information
    current_round_number = player_data.rounds_played + 1
    round_msg = f"""
## 🎯 Round {current_round_number} of 3

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

## 🎯 **Your Mission:**
**Write a BETTER prompt that will generate a MUCH better response!**

### 📋 **What to do:**
1. **Analyze the bad prompt** - What makes it unclear or ineffective?
2. **Use the COSTAR framework** (see Game Guide 📖) to improve it
3. **Type your improved prompt** in the chat box below
4. **Submit it** to see how much better your response is!
💡 **Tip:** Include as many COSTAR elements as possible in your improved prompt!

---

## ✍️ **Ready to improve?**
**Simply type your improved prompt below and press Enter:**

💡 **Example:** Instead of "Write about AI", try "Write a 300-word blog post about AI for business executives, using a professional tone and including 3 key benefits."
"""

    round_message = await cl.Message(content=round_msg).send()
    cl.user_session.set("main_message", round_message)
    cl.user_session.set("game_state", "waiting_for_improved_prompt")


async def handle_improved_prompt(improved_prompt: str, username: str):
    """Handle the user's improved prompt submission."""

    if not improved_prompt.strip():
        empty_prompt_message = await cl.Message(
            content="❌ **Your improved prompt cannot be empty.** Please try again.\n\n"
            "💡 **What to do:** Write a better version of the bad prompt above. See the Game Guide 📖 for the COSTAR framework.\n\n"
            "**Example:** Instead of 'Write about AI', try 'Write a 300-word blog post about AI for business executives, using a professional tone and including 3 key benefits.'",
            actions=[
                Action(name="stop", payload={"action": "stop"}, label="🛑 Stop Game"),
            ],
        ).send()
        cl.user_session.set("main_message", empty_prompt_message)
        return

    bad_prompt = cl.user_session.get("current_bad_prompt")
    if not bad_prompt:
        no_prompt_message = await cl.Message(
            content="❌ **Error: No current prompt found.** Something went wrong.",
            actions=[
                Action(
                    name="next", payload={"action": "next"}, label="🔄 Try New Round"
                ),
                Action(name="stop", payload={"action": "stop"}, label="🛑 Stop Game"),
            ],
        ).send()
        cl.user_session.set("main_message", no_prompt_message)
        return

    # Show initial processing message
    processing_msg = await cl.Message(
        content="⏳ **Processing your improved prompt...**\n\n"
        "🤖 Generating improved response...\n"
        "📊 Evaluating with LLM-as-a-judge...\n"
        "🎯 Calculating scores...\n\n"
        "*This may take a moment...*"
    ).send()

    try:
        # Get player data
        player_data = cl.user_session.get("player_data")
        current_round_number = player_data.rounds_played + 1

        # Generate improved response with proper context
        improved_response = await game.generate_improved_response(
            improved_prompt, bad_prompt
        )

        # Evaluate the improvement
        evaluation = await game.evaluator.evaluate_prompt_improvement(
            original_prompt=bad_prompt.bad_prompt,
            improved_prompt=improved_prompt,
            improved_response=improved_response,
            context=bad_prompt.context,
        )

        # Create game round
        game_round = GameRound(
            round_number=current_round_number,
            bad_prompt=bad_prompt,
            original_prompt=bad_prompt.bad_prompt,
            improved_prompt=improved_prompt,
            improved_response=improved_response,
            ragas_score=evaluation.total_score,
            feedback=evaluation.feedback,
        )

        # Update player in database immediately
        success = game.leaderboard_db.update_player_after_round(username, game_round)

        # Remove processing message
        await processing_msg.remove()

        if not success:
            await cl.Message(
                content="❌ **Error saving round results.** Please try again.",
                actions=[
                    Action(
                        name="stop", payload={"action": "stop"}, label="🛑 Stop Game"
                    ),
                ],
            ).send()
            return

        # Update player data in session
        updated_player_data = game.leaderboard_db.get_player_history(username)
        cl.user_session.set("player_data", updated_player_data)

        # Display results
        await display_round_results(game_round, username, updated_player_data)

    except Exception as e:
        # Remove processing message
        await processing_msg.remove()

        error_processing_message = await cl.Message(
            content=f"❌ **Error processing round:** {str(e)}\n\n"
            "Please try submitting your improved prompt again.",
            actions=[
                Action(name="stop", payload={"action": "stop"}, label="🛑 Stop Game"),
            ],
        ).send()
        cl.user_session.set("main_message", error_processing_message)
        logger.error(f"Error processing round for {username}: {e}")
        return


async def display_round_results(game_round: GameRound, username: str, player_data):
    """Display the results of a completed round."""

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

### 📈 **Your Progress:**
- **Rounds Played:** {player_data.rounds_played} of 3
- **Best Score So Far:** {player_data.final_score:.1f}/10
- **Rounds Remaining:** {player_data.rounds_remaining}
"""

    # Check if more rounds are available and add appropriate buttons
    if player_data.can_play_more_rounds:
        results_message = await cl.Message(
            content=results_msg,
            actions=[
                Action(name="next", payload={"action": "next"}, label="🚀 Next Round"),
                Action(name="stop", payload={"action": "stop"}, label="🛑 End Game"),
            ],
        ).send()
        cl.user_session.set("main_message", results_message)
        cl.user_session.set("game_state", "waiting_for_round_decision")
    else:
        await cl.Message(content=results_msg).send()
        await cl.Message(
            content="🎊 **You've completed all 3 rounds!** Showing your final results..."
        ).send()
        await show_completed_user_menu(player_data)


async def handle_round_decision(decision: str, username: str):
    """Handle player's decision between rounds."""

    decision = decision.lower().strip()

    if decision in ["next", "continue", "play"]:
        await start_new_round(username)
    elif decision in ["stop", "end", "quit", "finish"]:
        await end_game(username)
    else:
        choice_message = await cl.Message(
            content="🤔 **Please choose an action:**",
            actions=[
                Action(name="next", payload={"action": "next"}, label="🚀 Next Round"),
                Action(name="stop", payload={"action": "stop"}, label="🛑 End Game"),
            ],
        ).send()
        cl.user_session.set("main_message", choice_message)


async def end_game(username: str):
    """End the game and show final results."""

    success, message, final_results = game.end_game(username)

    if not success:
        await cl.Message(
            content=f"❌ **Error ending game:** {message}",
            actions=[
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 View Leaderboard",
                ),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 Statistics"
                ),
                Action(name="help", payload={"action": "help"}, label="❓ Help"),
            ],
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
"""

    final_message = await cl.Message(
        content=final_msg,
        actions=[
            Action(
                name="leaderboard",
                payload={"action": "leaderboard"},
                label="🏆 View Leaderboard",
            ),
            Action(name="stats", payload={"action": "stats"}, label="📊 Statistics"),
            Action(
                name="user_history",
                payload={"action": "user_history"},
                label="📜 User's History",
            ),
            Action(
                name="top_leaderboard_prompt",
                payload={"action": "top_leaderboard_prompt"},
                label="🎯 Top Leaderboard Prompt",
            ),
        ],
    ).send()

    cl.user_session.set("main_message", final_message)
    cl.user_session.set("game_state", "game_ended")


async def show_session_stats(username: str, in_game: bool = False):
    """Show current session statistics."""

    summary = game.get_session_summary(username)
    if not summary:
        await cl.Message(
            content="❌ **No active session found.**\n\n"
            "🎮 **Ready to start playing?** Enter your unique username!",
            actions=[
                Action(name="help", payload={"action": "help"}, label="❓ Help"),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
            ],
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

    stats_msg += "\n\n---\n\n"

    # Add appropriate buttons based on context
    actions = []
    if in_game and summary["can_play_more"]:
        actions = [
            Action(name="next", payload={"action": "next"}, label="🚀 Next Round"),
            Action(name="stop", payload={"action": "stop"}, label="🛑 End Game"),
            Action(
                name="leaderboard",
                payload={"action": "leaderboard"},
                label="🏆 Leaderboard",
            ),
        ]
        stats_msg += "🚀 **CONTINUE YOUR GAME:** Use the buttons below!"
    elif in_game and not summary["can_play_more"]:
        actions = [
            Action(name="stop", payload={"action": "stop"}, label="🏆 Final Results"),
            Action(
                name="leaderboard",
                payload={"action": "leaderboard"},
                label="🏆 Leaderboard",
            ),
        ]
        stats_msg += "🎊 **Game Complete!** View your final results!"
    else:
        actions = [
            Action(
                name="leaderboard",
                payload={"action": "leaderboard"},
                label="🏆 Leaderboard",
            ),
            Action(name="help", payload={"action": "help"}, label="❓ Help"),
        ]
        stats_msg += "🎮 **What's next?** Use the buttons below!"

    stats_message = await cl.Message(content=stats_msg, actions=actions).send()
    cl.user_session.set("main_message", stats_message)


async def show_leaderboard(in_game: bool = False, username: str = None):
    """Show the current leaderboard."""

    top_players = game.get_leaderboard(10)

    if not top_players:
        if in_game:
            await cl.Message(
                content="🏆 **Leaderboard is empty!** You could be the first!\n\n"
                "🎮 **YOUR GAME IS STILL ACTIVE** - Continue playing below!",
                actions=[
                    Action(
                        name="next", payload={"action": "next"}, label="🚀 Next Round"
                    ),
                    Action(
                        name="stop", payload={"action": "stop"}, label="🛑 End Game"
                    ),
                ],
            ).send()
        else:
            await cl.Message(
                content="🏆 **Leaderboard is empty!** Be the first to play and set a score!\n\n"
                "🎮 **Ready to start?** Enter your unique username to begin playing!",
                actions=[
                    Action(name="help", payload={"action": "help"}, label="❓ Help"),
                    Action(
                        name="stats", payload={"action": "stats"}, label="📊 Game Stats"
                    ),
                ],
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

    leaderboard_msg += "\n---\n\n"

    # Different navigation based on context
    actions = []
    if in_game:
        session = game.get_current_session(username) if username else None
        if session and session.can_play_more_rounds:
            actions = [
                Action(name="next", payload={"action": "next"}, label="🚀 Next Round"),
                Action(name="stop", payload={"action": "stop"}, label="🛑 End Game"),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 View Stats"
                ),
            ]
            leaderboard_msg += "🚀 **CONTINUE YOUR GAME:** Use the buttons below!"
        else:
            actions = [
                Action(
                    name="stop", payload={"action": "stop"}, label="🏆 Final Results"
                ),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 View Stats"
                ),
            ]
            leaderboard_msg += "🎊 **FINISH YOUR GAME:** See your final results!"
    else:
        actions = [
            Action(
                name="back_to_menu",
                payload={"action": "back_to_menu"},
                label="🏠 Back to Menu",
            ),
            Action(name="help", payload={"action": "help"}, label="❓ Help"),
            Action(name="stats", payload={"action": "stats"}, label="📊 Game Stats"),
        ]
        leaderboard_msg += "🎮 **Ready to continue?** Click the 'Back to Menu' button to return to your game!"

    leaderboard_message = await cl.Message(
        content=leaderboard_msg, actions=actions
    ).send()
    cl.user_session.set("main_message", leaderboard_message)


async def handle_special_commands(command: str):
    """Handle special commands like help, leaderboard, stats."""

    if command == "help":
        help_msg = """
# 🎮 Fix That Prompt - Game Guide

## 🎯 **How It Works:**
Each round, you receive a **poorly written prompt** with its **weak AI response**. Your job is to **improve the prompt** using the **COSTAR framework** to generate a better response. The more improvement you achieve, the higher your score!

## 📊 **Detailed Scoring:**
- **Prompt Quality (0-5 points):** Clarity, specificity, completeness
- **COSTAR Usage (0-3 points):** Framework adherence
- **Creativity Bonus (0-2 points):** Innovation and uniqueness
- **Maximum:** 10 points per round

## 🏆 **Game Rules:**
- Each username can play only **once**
- Up to **3 rounds** per game
- You can **stop after any round**
- Your **best round score** becomes your final score
- Top 10 players make the **leaderboard**

## 🎮 **Navigation:**
- **'🏠 Back to Menu'** - Return to your personal menu
- **'next'** - Play another round (during game)
- **'stop'** - End current game
- **'stats'** - View game statistics
- **'leaderboard'** - See top players

**Ready to continue? Click the 'Back to Menu' button to return to your game!**
"""
        await cl.Message(
            content=help_msg,
            actions=[
                Action(
                    name="back_to_menu",
                    payload={"action": "back_to_menu"},
                    label="🏠 Back to Menu",
                ),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
                Action(
                    name="stats", payload={"action": "stats"}, label="📊 Game Stats"
                ),
            ],
        ).send()

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

**Ready to continue? Click the 'Back to Menu' button to return to your game!**
"""
        await cl.Message(
            content=stats_msg,
            actions=[
                Action(
                    name="back_to_menu",
                    payload={"action": "back_to_menu"},
                    label="🏠 Back to Menu",
                ),
                Action(name="help", payload={"action": "help"}, label="❓ Help"),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
            ],
        ).send()


async def handle_post_game(message_content: str):
    """Handle messages after game has ended."""

    content = message_content.lower().strip()

    if content in ["leaderboard", "board", "rankings"]:
        await show_leaderboard()
    elif content in ["help", "info"]:
        await cl.Message(
            content="🎮 **Use the buttons below to continue!**",
            actions=[
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
                Action(
                    name="back_to_menu",
                    payload={"action": "back_to_menu"},
                    label="🏠 Back to Menu",
                ),
            ],
        ).send()
    elif content in ["stats"]:
        await handle_special_commands("stats")
    else:
        # For any other input, guide user to use buttons
        await cl.Message(
            content="🏁 **Use the buttons below to continue!**",
            actions=[
                Action(
                    name="back_to_menu",
                    payload={"action": "back_to_menu"},
                    label="🏠 Back to Menu",
                ),
                Action(
                    name="leaderboard",
                    payload={"action": "leaderboard"},
                    label="🏆 Leaderboard",
                ),
                Action(name="help", payload={"action": "help"}, label="❓ Help"),
            ],
        ).send()


if __name__ == "__main__":
    # This won't be called when running with chainlit run
    # but can be useful for testing
    logger.info("Starting Fix That Prompt game...")
