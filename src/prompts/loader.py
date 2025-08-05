"""Prompt loading utilities for the Fix That Prompt game."""

import json
import random
from pathlib import Path
from typing import List

from loguru import logger

from ..models.player_session import BadPrompt


class PromptLoader:
    """Loads and manages bad prompts for the game."""

    def __init__(self, prompts_file: str = "data/bad_prompts.json") -> None:
        """
        Initialize the prompt loader.

        Args:
            prompts_file: Path to the JSON file containing bad prompts
        """
        self.prompts_file = Path(prompts_file)
        self._prompts: List[BadPrompt] = []
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Load prompts from the JSON file."""
        try:
            with open(self.prompts_file, "r", encoding="utf-8") as f:
                prompt_data = json.load(f)

            self._prompts = [
                BadPrompt(
                    id=item["id"],
                    category=item["category"],
                    bad_prompt=item["bad_prompt"],
                    weak_response=item["weak_response"],
                    context=item["context"],
                    expected_improvements=item["expected_improvements"],
                )
                for item in prompt_data
            ]

            logger.info(
                f"Loaded {len(self._prompts)} bad prompts from {self.prompts_file}"
            )

        except FileNotFoundError:
            logger.error(f"Prompts file not found: {self.prompts_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in prompts file: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing required field in prompts data: {e}")
            raise

    def get_random_prompt(self, exclude_ids: List[str] = None) -> BadPrompt:
        """
        Get a random bad prompt, optionally excluding specific IDs.

        Args:
            exclude_ids: List of prompt IDs to exclude from selection

        Returns:
            A randomly selected BadPrompt instance

        Raises:
            ValueError: If no prompts are available after exclusions
        """
        if exclude_ids is None:
            exclude_ids = []

        available_prompts = [
            prompt for prompt in self._prompts if prompt.id not in exclude_ids
        ]

        if not available_prompts:
            if exclude_ids:
                logger.warning(
                    "No prompts available after exclusions, using all prompts"
                )
                available_prompts = self._prompts
            else:
                raise ValueError("No prompts available")

        selected_prompt = random.choice(available_prompts)
        logger.debug(
            f"Selected prompt: {selected_prompt.id} ({selected_prompt.category})"
        )

        return selected_prompt

    def get_prompt_by_id(self, prompt_id: str) -> BadPrompt:
        """
        Get a specific prompt by its ID.

        Args:
            prompt_id: The ID of the prompt to retrieve

        Returns:
            The BadPrompt with the specified ID

        Raises:
            ValueError: If no prompt with the given ID is found
        """
        for prompt in self._prompts:
            if prompt.id == prompt_id:
                return prompt

        raise ValueError(f"No prompt found with ID: {prompt_id}")

    def get_prompts_by_category(self, category: str) -> List[BadPrompt]:
        """
        Get all prompts in a specific category.

        Args:
            category: The category to filter by

        Returns:
            List of BadPrompt instances in the specified category
        """
        category_prompts = [
            prompt
            for prompt in self._prompts
            if prompt.category.lower() == category.lower()
        ]

        logger.debug(f"Found {len(category_prompts)} prompts in category: {category}")
        return category_prompts

    def get_all_categories(self) -> List[str]:
        """
        Get all available prompt categories.

        Returns:
            List of unique category names
        """
        categories = list(set(prompt.category for prompt in self._prompts))
        return sorted(categories)

    @property
    def total_prompts(self) -> int:
        """Get the total number of available prompts."""
        return len(self._prompts)
