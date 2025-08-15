#!/usr/bin/env python3
"""
Migration script to transfer leaderboard data from JSON file to DynamoDB.

This script helps migrate existing leaderboard data from the JSON file format
to the new DynamoDB backend.

Usage:
    python scripts/migrate_to_dynamodb.py [--json-file path/to/leaderboard.json] [--dry-run]

Requirements:
    - AWS credentials configured (via AWS CLI, environment variables, or IAM role)
    - DynamoDB table created and accessible
    - DYNAMODB_TABLE_NAME environment variable set
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add the src directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from database.leaderboard_db import LeaderboardDB
    from database.dynamodb_leaderboard import DynamoDBLeaderboard
    from models.player_session import PlayerScore, GameRound, BadPrompt
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're running this script from the project root directory")
    print("   Example: python scripts/migrate_to_dynamodb.py")
    sys.exit(1)

from datetime import datetime


def load_json_data(json_file: str) -> Dict[str, Any]:
    """Load data from JSON file."""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ JSON file not found: {json_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON file: {e}")
        sys.exit(1)


def convert_json_to_player_scores(json_data: Dict[str, Any]) -> list[PlayerScore]:
    """Convert JSON data to PlayerScore objects."""
    players = []

    for player_data in json_data.get("players", []):
        # Deserialize rounds
        rounds = []
        for round_dict in player_data.get("rounds", []):
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

        # Create PlayerScore object
        player_score = PlayerScore(
            username=player_data["username"],
            rounds_remaining=player_data.get("rounds_remaining", 0),
            final_score=player_data.get("final_score", 0.0),
            rounds_played=player_data.get("rounds_played", 0),
            best_round_score=player_data.get("best_round_score", 0.0),
            total_rounds=player_data.get("total_rounds", 0),
            rounds=rounds,
            is_completed=player_data.get("is_completed", False),
            created_at=datetime.fromisoformat(
                player_data.get("created_at", datetime.now().isoformat())
            ),
            last_played=datetime.fromisoformat(
                player_data.get("last_played", datetime.now().isoformat())
            ),
        )
        players.append(player_score)

    return players


def migrate_data(json_file: str, dry_run: bool = False) -> None:
    """Migrate data from JSON to DynamoDB."""
    print("🚀 Starting migration from JSON to DynamoDB...")
    print(f"📁 JSON file: {json_file}")

    # Check environment
    table_name = os.getenv("DYNAMODB_TABLE_NAME")
    if not table_name:
        print("❌ DYNAMODB_TABLE_NAME environment variable not set")
        print("   Please set it to your DynamoDB table name")
        sys.exit(1)

    print(f"🗄️  DynamoDB table: {table_name}")

    # Load JSON data
    print("📖 Loading JSON data...")
    json_data = load_json_data(json_file)
    players_data = json_data.get("players", [])
    print(f"📊 Found {len(players_data)} players in JSON file")

    if not players_data:
        print("⚠️  No players found in JSON file. Nothing to migrate.")
        return

    # Convert to PlayerScore objects
    print("🔄 Converting data to PlayerScore objects...")
    players = convert_json_to_player_scores(json_data)

    if dry_run:
        print("🧪 DRY RUN MODE - No data will be written to DynamoDB")
        print("\n📋 Players to migrate:")
        for player in players:
            status = "✅ Completed" if player.is_completed else "🔄 Active"
            print(
                f"   • {player.username}: {player.final_score:.1f}/10 ({player.rounds_played} rounds) - {status}"
            )
        print(f"\n✅ Dry run completed. {len(players)} players would be migrated.")
        return

    # Initialize DynamoDB backend
    print("🔌 Connecting to DynamoDB...")
    try:
        dynamodb_backend = DynamoDBLeaderboard(table_name=table_name)
    except Exception as e:
        print(f"❌ Failed to connect to DynamoDB: {e}")
        print("   Please check your AWS credentials and table configuration")
        sys.exit(1)

    # Migrate each player
    print("📤 Migrating players to DynamoDB...")
    success_count = 0
    error_count = 0

    for i, player in enumerate(players, 1):
        try:
            print(f"   [{i}/{len(players)}] Migrating {player.username}...", end=" ")

            # Check if player already exists
            existing = dynamodb_backend.get_player_history(player.username)
            if existing:
                print("⚠️  Already exists (skipping)")
                continue

            # Create player in DynamoDB
            success = dynamodb_backend.create_or_update_player(player)
            if success:
                print("✅")
                success_count += 1
            else:
                print("❌ Failed")
                error_count += 1

        except Exception as e:
            print(f"❌ Error: {e}")
            error_count += 1

    print(f"\n📊 Migration completed:")
    print(f"   ✅ Successfully migrated: {success_count} players")
    if error_count > 0:
        print(f"   ❌ Errors: {error_count} players")

    # Verify migration
    print("🔍 Verifying migration...")
    total_in_dynamodb = dynamodb_backend.get_total_players()
    print(f"   📊 Total players in DynamoDB: {total_in_dynamodb}")

    if success_count > 0:
        print("\n🎉 Migration completed successfully!")
        print(
            "💡 You can now set DYNAMODB_TABLE_NAME in your .env file to use DynamoDB"
        )
        print(f"   Add this line: DYNAMODB_TABLE_NAME={table_name}")
    else:
        print("\n⚠️  No new players were migrated")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Migrate leaderboard data from JSON to DynamoDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate with default JSON file
  python scripts/migrate_to_dynamodb.py

  # Migrate with custom JSON file
  python scripts/migrate_to_dynamodb.py --json-file /path/to/custom/leaderboard.json

  # Dry run to see what would be migrated
  python scripts/migrate_to_dynamodb.py --dry-run

Environment Variables:
  DYNAMODB_TABLE_NAME    DynamoDB table name (required)
  AWS_REGION            AWS region (default: ap-southeast-1)
        """,
    )

    parser.add_argument(
        "--json-file",
        default="data/leaderboard.json",
        help="Path to JSON leaderboard file (default: data/leaderboard.json)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually writing to DynamoDB",
    )

    args = parser.parse_args()

    # Check if JSON file exists
    if not Path(args.json_file).exists():
        print(f"❌ JSON file not found: {args.json_file}")
        print("   Please specify a valid JSON file with --json-file")
        sys.exit(1)

    try:
        migrate_data(args.json_file, args.dry_run)
    except KeyboardInterrupt:
        print("\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
