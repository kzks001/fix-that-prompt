"""DynamoDB-based leaderboard implementation for Fix That Prompt game."""

import os
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from loguru import logger

from ..models.player_session import BadPrompt, GameRound, PlayerScore
from ..utils.logger import (
    log_dynamodb_error,
    log_dynamodb_operation,
    log_game_event,
)


class DynamoDBLeaderboard:
    """Manages leaderboard persistence using AWS DynamoDB."""

    def __init__(
        self, table_name: str | None = None, region: str = "ap-southeast-1"
    ) -> None:
        """
        Initialize the DynamoDB leaderboard.

        Args:
            table_name: DynamoDB table name (from environment if not provided)
            region: AWS region for DynamoDB
        """
        self.table_name = table_name or os.getenv(
            "DYNAMODB_TABLE_NAME", "fix-that-prompt-leaderboard"
        )
        self.region = region

        # Initialize DynamoDB client and resource
        try:
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self.table = self.dynamodb.Table(self.table_name)

            # Test the connection by checking if table exists
            self.table.load()
            logger.info(
                f"Initialized DynamoDB leaderboard with table: {self.table_name}"
            )

        except Exception as e:
            log_dynamodb_error("initialize", self.table_name, error=e)
            raise ConnectionError(
                f"Could not connect to DynamoDB table '{self.table_name}': {e}"
            )

    def _serialize_rounds(self, rounds: list[GameRound]) -> list[dict[str, Any]]:
        """Convert GameRound objects to DynamoDB-compatible dictionaries."""
        serialized_rounds = []
        for round_data in rounds:
            round_dict = {
                "round_number": round_data.round_number,
                "original_prompt": round_data.original_prompt,
                "improved_prompt": round_data.improved_prompt,
                "improved_response": round_data.improved_response,
                "ragas_score": Decimal(
                    str(round_data.ragas_score)
                ),  # DynamoDB requires Decimal for numbers
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

    def _deserialize_rounds(self, rounds_data: list[dict[str, Any]]) -> list[GameRound]:
        """Convert DynamoDB dictionaries back to GameRound objects."""
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
                ragas_score=float(
                    round_dict["ragas_score"]
                ),  # Convert Decimal back to float
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
        try:
            # Convert PlayerScore to DynamoDB item
            item = {
                "username": player_score.username,
                "rounds_remaining": player_score.rounds_remaining,
                "final_score": Decimal(str(player_score.final_score)),
                "rounds_played": player_score.rounds_played,
                "best_round_score": Decimal(str(player_score.best_round_score)),
                "total_rounds": player_score.total_rounds,
                "is_completed": player_score.is_completed,
                "created_at": player_score.created_at.isoformat(),
                "last_played": player_score.last_played.isoformat(),
                "rounds": self._serialize_rounds(player_score.rounds),
                "game_status": "completed" if player_score.is_completed else "active",
                "updated_at": datetime.now().isoformat(),
            }

            # Use put_item to create or replace the entire item
            self.table.put_item(Item=item)

            log_dynamodb_operation(
                "put_item", self.table_name, player_score.username, success=True
            )

            log_game_event(
                "player_updated",
                {
                    "username": player_score.username,
                    "final_score": float(player_score.final_score),
                    "rounds_remaining": player_score.rounds_remaining,
                    "is_completed": player_score.is_completed,
                },
            )

            logger.info(f"Successfully saved player: {player_score.username}")
            return True

        except ClientError as e:
            log_dynamodb_error(
                "put_item", self.table_name, player_score.username, error=e
            )
            return False
        except Exception as e:
            log_dynamodb_error(
                "put_item", self.table_name, player_score.username, error=e
            )
            return False

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
        try:
            response = self.table.get_item(Key={"username": username})
            exists = "Item" in response
            log_dynamodb_operation("get_item", self.table_name, username, success=True)
            return exists
        except ClientError as e:
            log_dynamodb_error("get_item", self.table_name, username, error=e)
            return False

    def get_top_players(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get the top players by score using the GSI.

        Args:
            limit: Maximum number of players to return

        Returns:
            List of player dictionaries sorted by score (highest first)
        """
        try:
            # Get all players (both completed and active) and sort by score
            all_players = []

            # Query completed players
            completed_response = self.table.query(
                IndexName="score-index",
                KeyConditionExpression=Key("game_status").eq("completed"),
                ScanIndexForward=False,
            )
            all_players.extend(completed_response.get("Items", []))

            # Query active players
            active_response = self.table.query(
                IndexName="score-index",
                KeyConditionExpression=Key("game_status").eq("active"),
                ScanIndexForward=False,
            )
            all_players.extend(active_response.get("Items", []))

            # Sort all players by final_score in descending order
            all_players.sort(key=lambda x: float(x.get("final_score", 0)), reverse=True)

            # Take the top 'limit' players
            players = all_players[:limit]

            # Convert Decimal values back to float and add rank
            top_players = []
            for i, player in enumerate(players):
                player_dict = self._convert_decimals_to_float(player)
                player_dict["rank"] = i + 1
                top_players.append(player_dict)

            logger.debug(
                f"Retrieved top {len(top_players)} players (including active players)"
            )
            return top_players

        except ClientError as e:
            log_dynamodb_error("query", self.table_name, error=e)
            return []

    def get_player_rank(self, username: str) -> int | None:
        """
        Get the rank of a specific player.

        Args:
            username: The username to find the rank for

        Returns:
            The player's rank (1-based) or None if not found
        """
        try:
            # Get the player's score first
            player = self.get_player_score(username)
            if not player:
                return None

            player_score = float(player["final_score"])

            # Count how many players (both completed and active) have a higher score
            higher_score_count = 0

            # Count completed players with higher scores
            completed_response = self.table.query(
                IndexName="score-index",
                KeyConditionExpression=Key("game_status").eq("completed")
                & Key("final_score").gt(Decimal(str(player_score))),
                Select="COUNT",
            )
            higher_score_count += completed_response["Count"]

            # Count active players with higher scores
            active_response = self.table.query(
                IndexName="score-index",
                KeyConditionExpression=Key("game_status").eq("active")
                & Key("final_score").gt(Decimal(str(player_score))),
                Select="COUNT",
            )
            higher_score_count += active_response["Count"]

            # Rank is the count of higher scores + 1
            return higher_score_count + 1

        except ClientError as e:
            log_dynamodb_error("query", self.table_name, username, error=e)
            return None

    def get_player_score(self, username: str) -> dict[str, Any] | None:
        """
        Get the score record for a specific player.

        Args:
            username: The username to look up

        Returns:
            The player's score dictionary or None if not found
        """
        try:
            response = self.table.get_item(Key={"username": username})

            if "Item" in response:
                return self._convert_decimals_to_float(response["Item"])
            return None

        except ClientError as e:
            log_dynamodb_error("get_item", self.table_name, username, error=e)
            return None

    def get_total_players(self) -> int:
        """Get the total number of players in the leaderboard."""
        try:
            response = self.table.scan(Select="COUNT")
            return response["Count"]
        except ClientError as e:
            log_dynamodb_error("scan", self.table_name, error=e)
            return 0

    def get_average_score(self) -> float:
        """Get the average score across all players (completed and active)."""
        try:
            all_players = []

            # Get completed players
            completed_response = self.table.query(
                IndexName="score-index",
                KeyConditionExpression=Key("game_status").eq("completed"),
                ProjectionExpression="final_score",
            )
            all_players.extend(completed_response.get("Items", []))

            # Get active players
            active_response = self.table.query(
                IndexName="score-index",
                KeyConditionExpression=Key("game_status").eq("active"),
                ProjectionExpression="final_score",
            )
            all_players.extend(active_response.get("Items", []))

            if not all_players:
                return 0.0

            total_score = sum(float(player["final_score"]) for player in all_players)
            return total_score / len(all_players)

        except ClientError as e:
            log_dynamodb_error("query", self.table_name, error=e)
            return 0.0

    def clear_leaderboard(self) -> None:
        """Clear all player data from the leaderboard (use with caution!)."""
        try:
            # Scan to get all items
            response = self.table.scan()
            items = response.get("Items", [])

            # Delete each item
            with self.table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={"username": item["username"]})

            log_game_event("leaderboard_cleared", {})
            logger.warning("DynamoDB leaderboard has been cleared!")

        except ClientError as e:
            log_dynamodb_error("scan", self.table_name, error=e)

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
        else:
            # Keep the current best score as final score
            player.final_score = player.best_round_score

        return self.create_or_update_player(player)

    def get_player_history(self, username: str) -> PlayerScore | None:
        """
        Get complete game history and status for a player.

        Args:
            username: The player's username

        Returns:
            PlayerScore object with complete history or None if not found
        """
        try:
            response = self.table.get_item(Key={"username": username})

            if "Item" not in response:
                return None

            item = response["Item"]

            # Deserialize the rounds data
            rounds = []
            if "rounds" in item and item["rounds"]:
                rounds = self._deserialize_rounds(item["rounds"])

            return PlayerScore(
                username=item["username"],
                rounds_remaining=item.get("rounds_remaining", 0),
                final_score=float(item.get("final_score", 0.0)),
                rounds_played=item.get("rounds_played", 0),
                best_round_score=float(item.get("best_round_score", 0.0)),
                total_rounds=item.get("total_rounds", 0),
                rounds=rounds,
                is_completed=item.get("is_completed", False),
                created_at=datetime.fromisoformat(
                    item.get("created_at", datetime.now().isoformat())
                ),
                last_played=datetime.fromisoformat(
                    item.get("last_played", datetime.now().isoformat())
                ),
            )

        except ClientError as e:
            log_dynamodb_error("get_item", self.table_name, username, error=e)
            return None

    def _convert_decimals_to_float(self, item: dict[str, Any]) -> dict[str, Any]:
        """Convert Decimal values in DynamoDB item to float for JSON serialization."""
        converted = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                converted[key] = float(value)
            elif isinstance(value, dict):
                converted[key] = self._convert_decimals_to_float(value)
            elif isinstance(value, list):
                converted[key] = [
                    (
                        self._convert_decimals_to_float(v)
                        if isinstance(v, dict)
                        else float(v) if isinstance(v, Decimal) else v
                    )
                    for v in value
                ]
            else:
                converted[key] = value
        return converted

    def backup_leaderboard(self, backup_table_name: str | None = None) -> str:
        """
        Create a backup of the current leaderboard to another DynamoDB table.

        Args:
            backup_table_name: Optional custom backup table name

        Returns:
            The name of the backup table
        """
        if backup_table_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_table_name = f"{self.table_name}_backup_{timestamp}"

        try:
            # This would require additional setup to create a backup table
            # For now, we'll log that backup was requested
            logger.info(
                f"Backup requested for table {self.table_name} to {backup_table_name}"
            )
            logger.info(
                "Note: DynamoDB backup should be handled through AWS backup services"
            )
            return backup_table_name

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            raise
