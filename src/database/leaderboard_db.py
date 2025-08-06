"""Leaderboard database implementation using JSON persistence."""

import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from loguru import logger

from ..models.player_session import PlayerScore, GameRound, BadPrompt
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

    def _ensure_data_structure(self, data: dict) -> dict:
        """Ensure the data has the correct structure."""
        if "players" not in data:
            data["players"] = []

        if "metadata" not in data:
            data["metadata"] = {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_games": len(data["players"]),
            }

        # Ensure all required metadata keys exist
        metadata_defaults = {
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "total_games": len(data["players"]),
        }

        for key, default_value in metadata_defaults.items():
            if key not in data["metadata"]:
                data["metadata"][key] = default_value

        return data

    def _write_data(self, data: dict) -> None:
        """Write data to the JSON file."""
        try:
            # Ensure data structure is correct
            data = self._ensure_data_structure(data)

            # Update metadata
            data["metadata"]["last_updated"] = datetime.now().isoformat()

            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug("Leaderboard data saved successfully")

        except Exception as e:
            logger.error(f"Error writing leaderboard data: {e}")
            raise

    def _serialize_rounds(self, rounds: List[GameRound]) -> List[dict]:
        """Convert GameRound objects to JSON-serializable dictionaries."""
        serialized_rounds = []
        for round_data in rounds:
            round_dict = {
                "round_number": round_data.round_number,
                "original_prompt": round_data.original_prompt,
                "improved_prompt": round_data.improved_prompt,
                "improved_response": round_data.improved_response,
                "ragas_score": round_data.ragas_score,
                "feedback": round_data.feedback,
                "timestamp": round_data.timestamp.isoformat(),
                "bad_prompt": {
                    "id": round_data.bad_prompt.id,
                    "category": round_data.bad_prompt.category,
                    "bad_prompt": round_data.bad_prompt.bad_prompt,
                    "weak_response": round_data.bad_prompt.weak_response,
                    "context": round_data.bad_prompt.context,
                    "expected_improvements": round_data.bad_prompt.expected_improvements,
                },
            }
            serialized_rounds.append(round_dict)
        return serialized_rounds

    def _deserialize_rounds(self, rounds_data: List[dict]) -> List[GameRound]:
        """Convert JSON dictionaries back to GameRound objects."""
        rounds = []
        for round_dict in rounds_data:
            bad_prompt = BadPrompt(
                id=round_dict["bad_prompt"]["id"],
                category=round_dict["bad_prompt"]["category"],
                bad_prompt=round_dict["bad_prompt"]["bad_prompt"],
                weak_response=round_dict["bad_prompt"]["weak_response"],
                context=round_dict["bad_prompt"]["context"],
                expected_improvements=round_dict["bad_prompt"]["expected_improvements"],
            )

            game_round = GameRound(
                round_number=round_dict["round_number"],
                bad_prompt=bad_prompt,
                original_prompt=round_dict["original_prompt"],
                improved_prompt=round_dict["improved_prompt"],
                improved_response=round_dict["improved_response"],
                ragas_score=round_dict["ragas_score"],
                feedback=round_dict["feedback"],
                timestamp=datetime.fromisoformat(round_dict["timestamp"]),
            )
            rounds.append(game_round)
        return rounds

    def create_or_update_player(self, player_score: PlayerScore) -> bool:
        """
        Create a new player or update existing player's progress.

        Args:
            player_score: The PlayerScore instance to save

        Returns:
            True if player was created/updated successfully
        """
        data = self._read_data()
        data = self._ensure_data_structure(data)

        # Convert PlayerScore to dictionary for JSON storage
        score_dict = {
            "username": player_score.username,
            "rounds_remaining": player_score.rounds_remaining,
            "final_score": player_score.final_score,
            "rounds_played": player_score.rounds_played,
            "best_round_score": player_score.best_round_score,
            "total_rounds": player_score.total_rounds,
            "is_completed": player_score.is_completed,
            "created_at": player_score.created_at.isoformat(),
            "last_played": player_score.last_played.isoformat(),
            "rank": None,  # Will be calculated when retrieving top scores
            "rounds": self._serialize_rounds(player_score.rounds),
        }

        # Check if player already exists
        existing_index = None
        for i, player in enumerate(data["players"]):
            if player["username"].lower() == player_score.username.lower():
                existing_index = i
                break

        if existing_index is not None:
            # Update existing player
            data["players"][existing_index] = score_dict
            logger.info(f"Updated player: {player_score.username}")
        else:
            # Add new player
            data["players"].append(score_dict)
            data["metadata"]["total_games"] += 1
            logger.info(f"Created new player: {player_score.username}")

        self._write_data(data)

        log_game_event(
            "player_updated",
            {
                "username": player_score.username,
                "final_score": player_score.final_score,
                "rounds_remaining": player_score.rounds_remaining,
                "is_completed": player_score.is_completed,
            },
        )

        return True

    def add_player_score(self, player_score: PlayerScore) -> bool:
        """Legacy method for backward compatibility - calls create_or_update_player."""
        return self.create_or_update_player(player_score)

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
        data = self._ensure_data_structure(data)

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

    def get_or_create_player(self, username: str) -> PlayerScore:
        """
        Get existing player or create a new one with 3 rounds remaining.

        Args:
            username: The player's username

        Returns:
            PlayerScore object (existing or newly created)
        """
        existing_player = self.get_player_history(username)
        if existing_player:
            return existing_player

        # Create new player
        new_player = PlayerScore(username=username)
        self.create_or_update_player(new_player)
        return new_player

    def update_player_after_round(
        self, username: str, completed_round: GameRound
    ) -> bool:
        """
        Update a player's progress after completing a round.

        Args:
            username: The player's username
            completed_round: The GameRound that was just completed

        Returns:
            True if update was successful
        """
        player = self.get_player_history(username)
        if not player:
            logger.error(f"Player {username} not found for round update")
            return False

        # Add the new round
        player.rounds.append(completed_round)
        player.rounds_played = len(player.rounds)
        player.total_rounds = len(player.rounds)
        player.rounds_remaining = max(0, 3 - player.rounds_played)
        player.is_completed = player.rounds_remaining == 0
        player.last_played = datetime.now()

        # Update best scores
        if completed_round.ragas_score > player.best_round_score:
            player.best_round_score = completed_round.ragas_score
            player.final_score = completed_round.ragas_score

        return self.create_or_update_player(player)

    def get_player_history(self, username: str) -> Optional[PlayerScore]:
        """
        Get complete game history and status for a player.

        Args:
            username: The player's username

        Returns:
            PlayerScore object with complete history or None if not found
        """
        data = self._read_data()
        data = self._ensure_data_structure(data)

        for player in data["players"]:
            if player["username"].lower() == username.lower():
                # Deserialize the rounds data
                rounds = []
                if "rounds" in player and player["rounds"]:
                    rounds = self._deserialize_rounds(player["rounds"])

                return PlayerScore(
                    username=player["username"],
                    rounds_remaining=player.get("rounds_remaining", 0),
                    final_score=player.get("final_score", 0.0),
                    rounds_played=player.get("rounds_played", 0),
                    best_round_score=player.get("best_round_score", 0.0),
                    total_rounds=player.get("total_rounds", 0),
                    rounds=rounds,
                    is_completed=player.get("is_completed", False),
                    created_at=datetime.fromisoformat(
                        player.get(
                            "created_at",
                            player.get("timestamp", datetime.now().isoformat()),
                        )
                    ),
                    last_played=datetime.fromisoformat(
                        player.get(
                            "last_played",
                            player.get("timestamp", datetime.now().isoformat()),
                        )
                    ),
                )

        return None

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
