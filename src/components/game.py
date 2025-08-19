"""Core game logic for Fix That Prompt game."""

from langchain_openai import ChatOpenAI
from loguru import logger

from ..components.session_manager import SessionManager
from ..database.leaderboard_db import LeaderboardDB
from ..evaluators.ragas_wrapper import RAGASPromptEvaluator
from ..models.player_session import (
    BadPrompt,
    GameRound,
    PlayerSession,
)
from ..prompts.loader import PromptLoader
from ..utils.logger import log_game_event, log_player_action, log_score_event


class FixThatPromptGame:
    """Core game logic and orchestration."""

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        prompts_file: str = "data/bad_prompts.json",
        leaderboard_file: str = "data/leaderboard.json",
    ) -> None:
        """
        Initialize the game.

        Args:
            model_name: OpenAI model for LLM operations
            prompts_file: Path to bad prompts JSON file
            leaderboard_file: Path to leaderboard JSON file
        """
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=0.7)

        # Initialize components
        self.prompt_loader = PromptLoader(prompts_file)
        self.leaderboard_db = LeaderboardDB(leaderboard_file)
        self.session_manager = SessionManager(self.leaderboard_db)
        self.evaluator = RAGASPromptEvaluator(model_name)

        # Game configuration

        logger.info(f"Game initialized with model: {model_name}")

    async def start_new_game(
        self, username: str
    ) -> tuple[bool, str, PlayerSession | None]:
        """
        Start a new game for a player.

        Args:
            username: The player's chosen username

        Returns:
            Tuple of (success, message, session)
        """
        return self.session_manager.start_new_session(username)

    def get_current_session(self, username: str) -> PlayerSession | None:
        """Get the current session for a player."""
        return self.session_manager.get_session(username)

    def get_session_for_history(self, username: str) -> PlayerSession | None:
        """Get a session (active or completed) for history purposes."""
        # First check active sessions
        active_session = self.session_manager.get_session(username)
        if active_session:
            return active_session

        # If not active, retrieve from database
        player_score = self.leaderboard_db.get_player_history(username)
        if player_score and player_score.rounds:
            # Convert PlayerScore back to PlayerSession format for compatibility
            session = PlayerSession(
                username=player_score.username,
                current_round=player_score.total_rounds + 1,
                max_rounds=3,
                rounds=player_score.rounds,
                is_active=False,
                created_at=player_score.created_at,
            )
            return session

        return None

    def get_current_round_prompt(self, username: str) -> BadPrompt | None:
        """
        Get the bad prompt for the current round.

        Args:
            username: The player's username

        Returns:
            BadPrompt for the current round or None if no active session
        """
        session = self.session_manager.get_session(username)
        if not session or not session.can_play_more_rounds:
            return None

        # Get prompts already used in this session
        used_prompt_ids = [round_.bad_prompt.id for round_ in session.rounds]

        # Get a random prompt that hasn't been used
        try:
            bad_prompt = self.prompt_loader.get_random_prompt(
                exclude_ids=used_prompt_ids
            )
            log_player_action(
                username,
                "prompt_selected",
                f"ID: {bad_prompt.id}, Category: {bad_prompt.category}",
            )
            return bad_prompt

        except ValueError as e:
            logger.error(f"Error getting prompt for {username}: {e}")
            # If no unused prompts, allow reuse
            return self.prompt_loader.get_random_prompt()

    async def generate_improved_response(
        self, improved_prompt: str, bad_prompt: BadPrompt, stream_callback=None
    ) -> str:
        """
        Generate an improved response using the player's improved prompt with proper context.

        Args:
            improved_prompt: The player's improved prompt
            bad_prompt: The original bad prompt with context and category
            stream_callback: Optional callback for streaming response chunks

        Returns:
            Generated response text
        """
        try:
            # Create a contextual prompt that ensures the LLM understands the task
            contextual_prompt = f"""
You are helping with a task in the category: {bad_prompt.category}

Context: {bad_prompt.context}

The user has provided this prompt for you to respond to:
"{improved_prompt}"

Please respond to this prompt as if you are completing the original task. Focus on providing a helpful response for the {bad_prompt.category.lower()} task described in the context above.

If the user's prompt is unclear, off-topic, or seems to be describing how to write prompts rather than actually giving you a task, please politely indicate that you need a clearer prompt for the {bad_prompt.category.lower()} task.
"""

            if stream_callback:
                # Use streaming if callback provided
                full_response = ""
                async for chunk in self.llm.astream(contextual_prompt):
                    if chunk.content:
                        full_response += chunk.content
                        await stream_callback(chunk.content, full_response)
                return full_response
            else:
                # Use regular invocation
                response = await self.llm.ainvoke(contextual_prompt)
                return response.content

        except Exception as e:
            logger.error(f"Error generating improved response: {e}")
            return f"Error generating response: {str(e)}"

    async def submit_round(
        self, username: str, bad_prompt: BadPrompt, improved_prompt: str
    ) -> tuple[bool, str, GameRound | None]:
        """
        Submit an improved prompt for evaluation and scoring.

        Args:
            username: The player's username
            bad_prompt: The original bad prompt
            improved_prompt: The player's improved prompt

        Returns:
            Tuple of (success, message, completed_round)
        """
        session = self.session_manager.get_session(username)
        if not session:
            return False, "No active session found", None

        if not session.can_play_more_rounds:
            return False, "No more rounds available", None

        if not improved_prompt.strip():
            return False, "Improved prompt cannot be empty", None

        try:
            log_player_action(
                username, "round_submitted", f"Round {session.current_round}"
            )

            # Generate improved response
            logger.info(f"Generating improved response for {username}")
            improved_response = await self.generate_improved_response(
                improved_prompt, bad_prompt
            )

            # Evaluate the improvement
            logger.info(f"Evaluating prompt improvement for {username}")
            evaluation = await self.evaluator.evaluate_prompt_improvement(
                original_prompt=bad_prompt.bad_prompt,
                improved_prompt=improved_prompt,
                improved_response=improved_response,
                context=bad_prompt.context,
            )

            # Create game round
            game_round = GameRound(
                round_number=session.current_round,
                bad_prompt=bad_prompt,
                original_prompt=bad_prompt.bad_prompt,
                improved_prompt=improved_prompt,
                improved_response=improved_response,
                ragas_score=evaluation.total_score,
                feedback=evaluation.feedback,
            )

            # Add round to session
            session.add_round(game_round)

            log_score_event(username, session.current_round - 1, evaluation.total_score)
            log_game_event(
                "round_completed",
                {
                    "username": username,
                    "round": game_round.round_number,
                    "score": evaluation.total_score,
                    "category": bad_prompt.category,
                },
            )

            logger.info(
                f"Round {game_round.round_number} completed for {username} - Score: {evaluation.total_score:.2f}"
            )

            return (
                True,
                f"Round {game_round.round_number} completed successfully!",
                game_round,
            )

        except Exception as e:
            logger.error(f"Error processing round for {username}: {e}")
            return False, f"Error processing round: {str(e)}", None

    def can_play_another_round(self, username: str) -> bool:
        """
        Check if a player can play another round.

        Args:
            username: The player's username

        Returns:
            True if another round can be played
        """
        session = self.session_manager.get_session(username)
        return session is not None and session.can_play_more_rounds

    def get_session_summary(self, username: str) -> dict[str, any] | None:
        """
        Get a summary of the player's current session.

        Args:
            username: The player's username

        Returns:
            Dictionary with session summary or None if no session
        """
        session = self.session_manager.get_session(username)
        if not session:
            return None

        return {
            "username": session.username,
            "current_round": session.current_round,
            "max_rounds": session.max_rounds,
            "rounds_completed": len(session.rounds),
            "can_play_more": session.can_play_more_rounds,
            "best_score": session.best_score,
            "rounds": [
                {
                    "round_number": r.round_number,
                    "category": r.bad_prompt.category,
                    "score": r.ragas_score,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in session.rounds
            ],
        }

    def end_game(self, username: str) -> tuple[bool, str, dict[str, any] | None]:
        """
        End the game for a player and return final results.

        Args:
            username: The player's username

        Returns:
            Tuple of (success, message, final_results)
        """
        session = self.session_manager.get_session(username)
        if not session:
            return False, "No active session found", None

        # End the session and save score
        success, message, final_score = self.session_manager.end_session(username)

        if not success:
            return False, message, None

        # Get leaderboard position
        rank = self.leaderboard_db.get_player_rank(username)
        top_players = self.leaderboard_db.get_top_players(10)

        final_results = {
            "final_score": final_score.final_score,
            "rounds_played": final_score.rounds_played,
            "best_round_score": final_score.best_round_score,
            "rank": rank,
            "total_players": self.leaderboard_db.get_total_players(),
            "top_players": top_players,
            "is_top_10": rank <= 10 if rank else False,
        }

        log_game_event(
            "game_ended",
            {
                "username": username,
                "final_score": final_score.final_score,
                "rank": rank,
            },
        )

        return True, "Game ended successfully!", final_results

    def get_leaderboard(self, limit: int = 10) -> list[dict[str, any]]:
        """
        Get the current leaderboard.

        Args:
            limit: Maximum number of players to return

        Returns:
            List of player records from leaderboard
        """
        return self.leaderboard_db.get_top_players(limit)

    def get_game_stats(self) -> dict[str, any]:
        """
        Get overall game statistics.

        Returns:
            Dictionary with game statistics
        """
        session_stats = self.session_manager.get_session_stats()

        return {
            "total_prompts_available": self.prompt_loader.total_prompts,
            "prompt_categories": self.prompt_loader.get_all_categories(),
            "total_players": self.leaderboard_db.get_total_players(),
            "average_score": self.leaderboard_db.get_average_score(),
            "active_sessions": session_stats["active_sessions"],
            "active_players": session_stats.get("usernames", []),
        }

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up old inactive sessions."""
        return self.session_manager.cleanup_inactive_sessions(max_age_hours)
