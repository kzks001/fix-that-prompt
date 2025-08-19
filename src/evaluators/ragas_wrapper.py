"""LLM-as-a-judge evaluation wrapper for scoring prompt improvements."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from loguru import logger

from ..utils.logger import log_game_event


@dataclass
class EvaluationResult:
    """Result from a single evaluation metric."""

    score: float
    max_score: float
    reasoning: str


@dataclass
class PromptEvaluation:
    """Results of prompt evaluation."""

    total_score: float
    prompt_quality_score: float
    costar_usage_score: float
    creativity_score: float
    feedback: str
    breakdown: dict[str, float]


class BaseEvaluator(ABC):
    """Base class for all metric evaluators."""

    def __init__(self, model_name: str = "gpt-4o-mini"):
        """Initialize the evaluator with an LLM model."""
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=0.1)

    @abstractmethod
    def get_evaluation_prompt(self) -> str:
        """Get the evaluation prompt template for this metric."""
        ...

    @abstractmethod
    def get_max_score(self) -> float:
        """Get the maximum possible score for this metric."""
        ...

    def _extract_score(self, response_text: str) -> float:
        """Extract score from the evaluator's response."""
        lines = response_text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("Score:"):
                try:
                    score_text = line.replace("Score:", "").strip()
                    return float(score_text)
                except ValueError:
                    continue
            elif any(char.isdigit() for char in line) and len(line) < 10:
                try:
                    numbers = [
                        float(s) for s in line.split() if s.replace(".", "").isdigit()
                    ]
                    if numbers and 0 <= numbers[0] <= self.get_max_score():
                        return numbers[0]
                except ValueError:
                    continue

        logger.warning(
            f"Could not extract score from response: {response_text[:100]}..."
        )
        return 0.0

    async def evaluate(
        self, original_prompt: str, improved_prompt: str, context: str
    ) -> EvaluationResult:
        """Evaluate the prompt improvement for this metric."""
        try:
            evaluation_prompt = self.get_evaluation_prompt().format(
                original_prompt=original_prompt,
                improved_prompt=improved_prompt,
                context=context,
            )

            response = await self.llm.ainvoke(evaluation_prompt)
            response_text = response.content

            score = self._extract_score(response_text)

            return EvaluationResult(
                score=score, max_score=self.get_max_score(), reasoning=response_text
            )

        except Exception as e:
            logger.error(f"Error in {self.__class__.__name__}: {e}")
            return EvaluationResult(
                score=0.0,
                max_score=self.get_max_score(),
                reasoning=f"Error during evaluation: {str(e)}",
            )


class PromptQualityEvaluator(BaseEvaluator):
    """Evaluator for prompt quality and clarity."""

    def get_max_score(self) -> float:
        return 5.0

    def get_evaluation_prompt(self) -> str:
        return """
You are evaluating a user's attempt to improve a bad prompt.

ORIGINAL BAD PROMPT: "{original_prompt}"
CONTEXT (provided by the game, NOT by the user): {context}
USER'S IMPROVED PROMPT (what you are evaluating): "{improved_prompt}"

Your job is to score ONLY the user's improved prompt (the text between quotes above) from 0-5 points.

CRITICAL REQUIREMENTS FOR THE USER'S IMPROVED PROMPT:
1. It must be an actual prompt that could be given to an AI to complete the same task as the original
2. It must be significantly better than the original bad prompt
3. It must stay within the same topic/domain as the original task
4. It should NOT be a description or explanation of how to write prompts

AUTOMATIC 0 POINTS if the user's improved prompt is:
- Just describing what COSTAR framework is (not applying it)
- Not actually a usable prompt for the task
- Completely different topic than the original
- Generic instructions about prompt writing
- Single words or meaningless phrases

SCORING:
- 5 points: Excellent prompt that dramatically improves the original, highly specific and actionable
- 4 points: Good prompt with clear improvements, specific and usable
- 3 points: Decent prompt with some improvements
- 2 points: Minor improvements but still unclear or incomplete
- 1 point: Barely better than original or very poor quality
- 0 points: No actual improvement, wrong topic, or not a real prompt

Start your response with "Score: X" then explain why, focusing on whether this is actually a usable prompt for the intended task.
Keep your response short and concise, at most 2 sentences.
"""


class COSTARUsageEvaluator(BaseEvaluator):
    """Evaluator for COSTAR framework usage."""

    def get_max_score(self) -> float:
        return 3.0

    def get_evaluation_prompt(self) -> str:
        return """
You are evaluating how well a user applied the COSTAR framework to improve a bad prompt.

ORIGINAL BAD PROMPT: "{original_prompt}"
CONTEXT (provided by the game, NOT by the user): {context}
USER'S IMPROVED PROMPT (what you are evaluating): "{improved_prompt}"

Your job is to score ONLY the user's improved prompt for actual COSTAR framework usage (0-3 points).

COSTAR Elements to look for IN THE USER'S IMPROVED PROMPT:
- Context: Does the user provide relevant background/context?
- Objective: Does the user specify clear goals/outcomes?
- Style: Does the user specify format, structure, or style preferences?
- Tone: Does the user specify the desired tone/voice?
- Audience: Does the user identify the target audience?
- Response: Does the user specify the desired response format?

AUTOMATIC 0 POINTS if the user's improved prompt is:
- Just explaining what COSTAR framework IS (not using it)
- Not actually applying COSTAR to the task
- Wrong topic completely
- Generic framework descriptions
- Copy-pasted COSTAR definitions

SCORING:
- 3 points: Uses 4+ COSTAR elements effectively IN their actual prompt for the task
- 2 points: Uses 2-3 COSTAR elements clearly IN their actual prompt
- 1 point: Uses 1 COSTAR element clearly IN their actual prompt
- 0 points: No actual COSTAR application OR just describing what COSTAR is

Start your response with "Score: X" then identify which specific COSTAR elements were actually applied in the user's prompt.
Keep your response short and concise, at most 2 sentences.
"""


class CreativityEvaluator(BaseEvaluator):
    """Evaluator for creativity and innovation."""

    def get_max_score(self) -> float:
        return 2.0

    def get_evaluation_prompt(self) -> str:
        return """
You are evaluating the creativity and innovation in a user's prompt improvement.

ORIGINAL BAD PROMPT: "{original_prompt}"
CONTEXT (provided by the game, NOT by the user): {context}
USER'S IMPROVED PROMPT (what you are evaluating): "{improved_prompt}"

Your job is to score ONLY the user's improved prompt for creativity and innovation (0-2 points).

AUTOMATIC 0 POINTS if the user's improved prompt is:
- Just explaining what COSTAR framework is (no creativity in descriptions)
- Not actually a prompt for the task
- Copy-pasted framework definitions
- Generic instructions about writing
- Wrong topic completely

SCORING (only if it's actually a usable prompt for the task):
- 2 points: Highly creative approach, innovative techniques, novel formatting for the specific task
- 1 point: Some creative elements or unique approaches for the task
- 0 points: No creativity, generic, or not actually a prompt for the task

Start your response with "Score: X" then explain in whether this shows creativity in solving the actual task.
Keep your response short and concise, at most 2 sentences.
"""


class RAGASPromptEvaluator:
    """Orchestrator for all metric evaluators."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        """
        Initialize the evaluator with separate metric evaluators.

        Args:
            model_name: The OpenAI model to use for evaluation
        """
        self.model_name = model_name

        # Initialize separate evaluators for each metric
        self.prompt_quality_evaluator = PromptQualityEvaluator(model_name)
        self.costar_usage_evaluator = COSTARUsageEvaluator(model_name)
        self.creativity_evaluator = CreativityEvaluator(model_name)

        logger.info(f"Initialized LLM evaluator with model: {model_name}")
        logger.info("Using separate evaluators for each metric")

    async def evaluate_prompt_improvement(
        self,
        original_prompt: str,
        improved_prompt: str,
        improved_response: str,
        context: str,
    ) -> PromptEvaluation:
        """
        Evaluate a prompt improvement using separate metric evaluators concurrently.

        Args:
            original_prompt: The original bad prompt
            improved_prompt: The user's improved prompt
            improved_response: The LLM response to the improved prompt
            context: The context/scenario for the prompt

        Returns:
            PromptEvaluation with scores and feedback
        """
        logger.info("Starting prompt evaluation with separate evaluators")

        try:
            # Evaluate all metrics concurrently using separate evaluators
            tasks = [
                self.prompt_quality_evaluator.evaluate(
                    original_prompt, improved_prompt, context
                ),
                self.costar_usage_evaluator.evaluate(
                    original_prompt, improved_prompt, context
                ),
                self.creativity_evaluator.evaluate(
                    original_prompt, improved_prompt, context
                ),
            ]

            results = await asyncio.gather(*tasks)

            prompt_quality_result = results[0]
            costar_result = results[1]
            creativity_result = results[2]

            # Calculate total score
            total_score = (
                prompt_quality_result.score
                + costar_result.score
                + creativity_result.score
            )

            # Generate comprehensive feedback
            feedback = self._generate_comprehensive_feedback(
                prompt_quality_result,
                costar_result,
                creativity_result,
                total_score,
            )

            # Create breakdown
            breakdown = {
                "prompt_quality": prompt_quality_result.score,
                "costar_usage": costar_result.score,
                "creativity": creativity_result.score,
                "total": total_score,
            }

            evaluation = PromptEvaluation(
                total_score=total_score,
                prompt_quality_score=prompt_quality_result.score,
                costar_usage_score=costar_result.score,
                creativity_score=creativity_result.score,
                feedback=feedback,
                breakdown=breakdown,
            )

            log_game_event(
                "prompt_evaluated", {"total_score": total_score, "breakdown": breakdown}
            )

            logger.info(f"Evaluation completed - Total score: {total_score:.2f}/10")
            logger.info(
                f"Individual scores: Quality={prompt_quality_result.score}, COSTAR={costar_result.score}, Creativity={creativity_result.score}"
            )
            return evaluation

        except Exception as e:
            logger.error(f"Error during prompt evaluation: {e}")

            # Return minimal evaluation on error
            return PromptEvaluation(
                total_score=0.0,
                prompt_quality_score=0.0,
                costar_usage_score=0.0,
                creativity_score=0.0,
                feedback=f"Evaluation failed: {str(e)}",
                breakdown={"error": str(e)},
            )

    def _generate_comprehensive_feedback(
        self,
        prompt_quality_result: EvaluationResult,
        costar_result: EvaluationResult,
        creativity_result: EvaluationResult,
        total_score: float,
    ) -> str:
        """Generate comprehensive feedback from individual evaluation results."""

        feedback_parts = [
            f"**🎯 Total Score: {total_score:.1f}/10**",
            "",
            f"**📝 Prompt Quality: {prompt_quality_result.score:.1f}/{prompt_quality_result.max_score}**",
            prompt_quality_result.reasoning,
            "",
            f"**⭐ COSTAR Framework Usage: {costar_result.score:.1f}/{costar_result.max_score}**",
            costar_result.reasoning,
            "",
            f"**💡 Creativity Bonus: {creativity_result.score:.1f}/{creativity_result.max_score}**",
            creativity_result.reasoning,
            "",
            self._get_performance_message(total_score),
        ]

        return "\n".join(feedback_parts)

    def _get_performance_message(self, total_score: float) -> str:
        """Get encouraging message based on total score."""
        if total_score >= 9:
            return "🏆 **Outstanding!** You've mastered prompt engineering!"
        elif total_score >= 7:
            return "🎉 **Excellent work!** Your prompt improvement skills are strong!"
        elif total_score >= 5:
            return "👍 **Good job!** You're on the right track with prompt improvement!"
        elif total_score >= 3:
            return "📚 **Keep practicing!** Consider focusing more on the COSTAR framework!"
        else:
            return "🎯 **Don't give up!** Review the COSTAR framework and try again!"
