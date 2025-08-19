"""Data models for player sessions and game rounds."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class BadPrompt:
    """Represents a bad prompt scenario with context."""

    id: str
    category: str
    bad_prompt: str
    weak_response: str
    context: str
    expected_improvements: List[str]


@dataclass
class GameRound:
    """Represents a single round of the game."""

    round_number: int
    bad_prompt: BadPrompt
    original_prompt: str
    improved_prompt: str
    improved_response: str
    ragas_score: float
    feedback: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PlayerScore:
    """Represents a player's progress and history with persistent round tracking."""

    username: str
    rounds_remaining: int = 3  # Starts at 3, decrements with each round played
    final_score: float = 0.0  # Best score achieved so far
    rounds_played: int = 0
    best_round_score: float = 0.0
    total_rounds: int = 0
    rounds: List[GameRound] = field(default_factory=list)
    is_completed: bool = False  # True when all 3 rounds are finished
    created_at: datetime = field(default_factory=datetime.now)
    last_played: datetime = field(default_factory=datetime.now)

    @property
    def can_play_more_rounds(self) -> bool:
        """Check if player can play more rounds."""
        return self.rounds_remaining > 0 and not self.is_completed


@dataclass
class PlayerSession:
    """Manages a complete player session through the game."""

    username: str
    current_round: int = 1
    max_rounds: int = 3
    rounds: List[GameRound] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def best_score(self) -> float:
        """Get the best score across all rounds."""
        if not self.rounds:
            return 0.0
        return max(round_.ragas_score for round_ in self.rounds)

    @property
    def can_play_more_rounds(self) -> bool:
        """Check if player can play more rounds."""
        return self.current_round <= self.max_rounds and self.is_active

    def add_round(self, game_round: GameRound) -> None:
        """Add a completed round to the session."""
        self.rounds.append(game_round)
        self.current_round += 1

    def end_session(self) -> PlayerScore:
        """End the session and return current progress (may not be complete game)."""
        self.is_active = False
        rounds_completed = len(self.rounds)
        is_game_complete = rounds_completed >= self.max_rounds

        return PlayerScore(
            username=self.username,
            rounds_remaining=max(0, self.max_rounds - rounds_completed),
            final_score=self.best_score,
            rounds_played=rounds_completed,
            best_round_score=self.best_score,
            total_rounds=rounds_completed,
            rounds=self.rounds.copy(),
            is_completed=is_game_complete,
            last_played=datetime.now(),
        )
