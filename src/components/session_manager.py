"""Session management for Fix That Prompt game."""

from typing import Dict, Optional, List
from datetime import datetime

from loguru import logger

from ..models.player_session import PlayerSession, PlayerScore
from ..database.leaderboard_db import LeaderboardDB
from ..utils.logger import log_player_action, log_game_event


class SessionManager:
    """Manages player sessions and game state."""

    def __init__(self, leaderboard_db: LeaderboardDB) -> None:
        """
        Initialize the session manager.

        Args:
            leaderboard_db: Database instance for leaderboard operations
        """
        self.leaderboard_db = leaderboard_db
        self.active_sessions: Dict[str, PlayerSession] = {}
        logger.info("Session manager initialized")

    def start_new_session(
        self, username: str
    ) -> tuple[bool, str, Optional[PlayerSession]]:
        """
        Start a new game session for a player.

        Args:
            username: The player's chosen username

        Returns:
            Tuple of (success, message, session)
        """
        if not username or not username.strip():
            return False, "Username cannot be empty", None

        username = username.strip()

        # Check if username already exists in leaderboard
        if self.leaderboard_db.username_exists(username):
            log_player_action(username, "duplicate_username_attempt")
            return (
                False,
                f"Username '{username}' has already played. Choose a different username.",
                None,
            )

        # Check if user has an active session
        if username in self.active_sessions:
            log_player_action(username, "existing_session_found")
            return (
                False,
                f"You already have an active session. Continue playing or end your current game.",
                self.active_sessions[username],
            )

        # Create new session
        session = PlayerSession(username=username)
        self.active_sessions[username] = session

        log_player_action(username, "session_started")
        logger.info(f"Started new session for player: {username}")

        return True, f"Welcome {username}! Your game session has started.", session

    def get_session(self, username: str) -> Optional[PlayerSession]:
        """
        Get an active session for a player.

        Args:
            username: The player's username

        Returns:
            The PlayerSession if it exists and is active, None otherwise
        """
        return self.active_sessions.get(username)

    def end_session(self, username: str) -> tuple[bool, str, Optional[PlayerScore]]:
        """
        End a player's session and save their score.

        Args:
            username: The player's username

        Returns:
            Tuple of (success, message, final_score)
        """
        session = self.active_sessions.get(username)
        if not session:
            return False, "No active session found", None

        # Create final score
        final_score = session.end_session()

        # Save to leaderboard
        success = self.leaderboard_db.add_player_score(final_score)
        if not success:
            logger.error(f"Failed to save score for {username}")
            return False, "Error saving score to leaderboard", final_score

        # Remove from active sessions (history now stored in database)
        del self.active_sessions[username]

        log_player_action(
            username,
            "session_ended",
            f"Final score: {final_score.final_score:.2f}, Rounds: {final_score.rounds_played}",
        )

        logger.info(
            f"Ended session for {username} - Final score: {final_score.final_score:.2f}"
        )

        return True, "Session ended successfully", final_score

    def get_active_sessions_count(self) -> int:
        """Get the number of currently active sessions."""
        return len(self.active_sessions)

    def get_active_usernames(self) -> List[str]:
        """Get list of all currently active usernames."""
        return list(self.active_sessions.keys())

    def cleanup_inactive_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up old inactive sessions.

        Args:
            max_age_hours: Maximum age of a session in hours before cleanup

        Returns:
            Number of sessions cleaned up
        """
        current_time = datetime.now()
        old_sessions = []

        for username, session in self.active_sessions.items():
            age_hours = (current_time - session.created_at).total_seconds() / 3600
            if age_hours > max_age_hours:
                old_sessions.append(username)

        # Remove old sessions
        for username in old_sessions:
            del self.active_sessions[username]
            logger.info(f"Cleaned up inactive session for: {username}")

        if old_sessions:
            log_game_event(
                "sessions_cleaned",
                {"count": len(old_sessions), "usernames": old_sessions},
            )

        return len(old_sessions)

    def get_session_stats(self) -> Dict[str, any]:
        """
        Get statistics about current sessions.

        Returns:
            Dictionary with session statistics
        """
        if not self.active_sessions:
            return {
                "active_sessions": 0,
                "total_rounds_in_progress": 0,
                "average_rounds_per_session": 0.0,
            }

        total_rounds = sum(
            len(session.rounds) for session in self.active_sessions.values()
        )

        return {
            "active_sessions": len(self.active_sessions),
            "total_rounds_in_progress": total_rounds,
            "average_rounds_per_session": (
                total_rounds / len(self.active_sessions)
                if self.active_sessions
                else 0.0
            ),
            "usernames": list(self.active_sessions.keys()),
        }

    def force_end_session(self, username: str) -> tuple[bool, str]:
        """
        Force end a session (admin function).

        Args:
            username: The username to force end

        Returns:
            Tuple of (success, message)
        """
        if username not in self.active_sessions:
            return False, "No active session found for this user"

        del self.active_sessions[username]

        log_player_action(username, "session_force_ended")
        logger.warning(f"Force ended session for: {username}")

        return True, f"Session for {username} has been force ended"

    def is_username_available(self, username: str) -> bool:
        """
        Check if a username is available for use.

        Args:
            username: The username to check

        Returns:
            True if username is available, False otherwise
        """
        if not username or not username.strip():
            return False

        username = username.strip()

        # Check leaderboard and active sessions
        return (
            not self.leaderboard_db.username_exists(username)
            and username not in self.active_sessions
        )
