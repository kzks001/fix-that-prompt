from flask import Flask, render_template, jsonify
import boto3
import os
from datetime import datetime
import json

app = Flask(__name__)

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")
table_name = os.getenv("DYNAMODB_TABLE_NAME", "fix-that-prompt-leaderboard")
table = dynamodb.Table(table_name)


@app.route("/")
def dashboard():
    """Main dashboard page"""
    return render_template("dashboard.html")


@app.route("/api/leaderboard")
def get_leaderboard():
    """API endpoint to get leaderboard data"""
    try:
        # Query the GSI for completed games, sorted by score
        response = table.query(
            IndexName="score-index",
            KeyConditionExpression="game_status = :status",
            ExpressionAttributeValues={":status": "completed"},
            ScanIndexForward=False,  # Sort in descending order (highest scores first)
            Limit=50,  # Get top 50 players
        )

        # Process the data
        players = []
        for item in response.get("Items", []):
            players.append(
                {
                    "username": item.get("username", "Unknown"),
                    "final_score": item.get("final_score", 0),
                    "game_status": item.get("game_status", "unknown"),
                    "completed_at": item.get("completed_at", ""),
                    "rounds_played": item.get("rounds_played", 0),
                }
            )

        return jsonify(
            {
                "success": True,
                "players": players,
                "total_players": len(players),
                "last_updated": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats")
def get_stats():
    """API endpoint to get game statistics"""
    try:
        # Get total completed games
        completed_response = table.query(
            IndexName="score-index",
            KeyConditionExpression="game_status = :status",
            ExpressionAttributeValues={":status": "completed"},
            Select="COUNT",
        )

        # Get active games
        active_response = table.query(
            IndexName="score-index",
            KeyConditionExpression="game_status = :status",
            ExpressionAttributeValues={":status": "active"},
            Select="COUNT",
        )

        return jsonify(
            {
                "success": True,
                "stats": {
                    "total_completed_games": completed_response.get("Count", 0),
                    "active_games": active_response.get("Count", 0),
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
