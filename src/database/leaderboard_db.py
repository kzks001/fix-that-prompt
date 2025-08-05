"""Leaderboard database implementation using JSON persistence."""

import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from loguru import logger

from ..models.player_session import PlayerScore
from ..utils.logger import log_game_event


class LeaderboardDB:
    """Manages leaderboard persistence using JSON storage."""

    def __init__(self, db_file: str = "data/leaderboard.json") -> None:
        """
        Initialize the leaderboard database.

        Args:
            db_file: Path to the JSON file for storing leaderboard data
        """
        self.db_file = Path(db_file)
        self.db_file.parent.mkdir(exist_ok=True)
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Ensure the database file exists with valid structure."""
        if not self.db_file.exists():
            initial_data = {
                "players": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "total_games": 0,
                },
            }
            self._write_data(initial_data)
            logger.info(f"Created new leaderboard database: {self.db_file}")

    def _read_data(self) -> dict:
        """Read data from the JSON file."""
        try:
            with open(self.db_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error reading leaderboard data: {e}")
            # Return default structure if file is corrupted
            return {
                "players": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "total_games": 0,
                },
            }

    def _write_data(self, data: dict) -> None:
        """Write data to the JSON file."""
        try:
            # Update metadata
            data["metadata"]["last_updated"] = datetime.now().isoformat()

            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug("Leaderboard data saved successfully")

        except Exception as e:
            logger.error(f"Error writing leaderboard data: {e}")
            raise

    def add_player_score(self, player_score: PlayerScore) -> bool:
        """
        Add a new player score to the leaderboard.

        Args:
            player_score: The PlayerScore instance to add

        Returns:
            True if score was added successfully, False if username exists
        """
        data = self._read_data()

        # Check if username already exists
        if self.username_exists(player_score.username):
            logger.warning(f"Username already exists: {player_score.username}")
            return False

        # Convert PlayerScore to dictionary for JSON storage
        score_dict = {
            "username": player_score.username,
            "final_score": player_score.final_score,
            "rounds_played": player_score.rounds_played,
            "best_round_score": player_score.best_round_score,
            "total_rounds": player_score.total_rounds,
            "timestamp": player_score.timestamp.isoformat(),
            "rank": None,  # Will be calculated when retrieving top scores
        }

        data["players"].append(score_dict)
        data["metadata"]["total_games"] += 1

        self._write_data(data)

        log_game_event(
            "player_score_added",
            {
                "username": player_score.username,
                "final_score": player_score.final_score,
                "rounds_played": player_score.rounds_played,
            },
        )

        logger.info(
            f"Added score for player: {player_score.username} "
            f"(Score: {player_score.final_score:.2f})"
        )

        return True

    def username_exists(self, username: str) -> bool:
        """
        Check if a username already exists in the leaderboard.

        Args:
            username: The username to check

        Returns:
            True if username exists, False otherwise
        """
        data = self._read_data()
        return any(
            player["username"].lower() == username.lower() for player in data["players"]
        )

    def get_top_players(self, limit: int = 10) -> List[dict]:
        """
        Get the top players by score.

        Args:
            limit: Maximum number of players to return

        Returns:
            List of player dictionaries sorted by score (highest first)
        """
        data = self._read_data()

        # Sort players by final_score in descending order
        sorted_players = sorted(
            data["players"], key=lambda x: x["final_score"], reverse=True
        )

        # Add rank information
        top_players = []
        for i, player in enumerate(sorted_players[:limit]):
            player_copy = player.copy()
            player_copy["rank"] = i + 1
            top_players.append(player_copy)

        logger.debug(f"Retrieved top {len(top_players)} players")
        return top_players

    def get_player_rank(self, username: str) -> Optional[int]:
        """
        Get the rank of a specific player.

        Args:
            username: The username to find the rank for

        Returns:
            The player's rank (1-based) or None if not found
        """
        data = self._read_data()

        # Sort all players by score
        sorted_players = sorted(
            data["players"], key=lambda x: x["final_score"], reverse=True
        )

        for i, player in enumerate(sorted_players):
            if player["username"].lower() == username.lower():
                return i + 1

        return None

    def get_player_score(self, username: str) -> Optional[dict]:
        """
        Get the score record for a specific player.

        Args:
            username: The username to look up

        Returns:
            The player's score dictionary or None if not found
        """
        data = self._read_data()

        for player in data["players"]:
            if player["username"].lower() == username.lower():
                return player

        return None

    def get_total_players(self) -> int:
        """Get the total number of players in the leaderboard."""
        data = self._read_data()
        return len(data["players"])

    def get_average_score(self) -> float:
        """Get the average score across all players."""
        data = self._read_data()

        if not data["players"]:
            return 0.0

        total_score = sum(player["final_score"] for player in data["players"])
        return total_score / len(data["players"])

    def clear_leaderboard(self) -> None:
        """Clear all player data from the leaderboard (use with caution!)."""
        data = self._read_data()
        data["players"] = []
        data["metadata"]["total_games"] = 0

        self._write_data(data)

        log_game_event("leaderboard_cleared", {})
        logger.warning("Leaderboard has been cleared!")

    def backup_leaderboard(self, backup_path: Optional[str] = None) -> str:
        """
        Create a backup of the current leaderboard.

        Args:
            backup_path: Optional custom backup file path

        Returns:
            The path to the backup file
        """
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"data/leaderboard_backup_{timestamp}.json"

        backup_file = Path(backup_path)
        backup_file.parent.mkdir(exist_ok=True)

        data = self._read_data()

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Leaderboard backed up to: {backup_file}")
        return str(backup_file)
