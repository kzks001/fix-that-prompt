"""LLM-as-a-judge evaluation wrapper for scoring prompt improvements."""

import asyncio
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from loguru import logger

from ..utils.logger import log_game_event


@dataclass
class PromptEvaluation:
    """Results of prompt evaluation."""

    total_score: float
    prompt_quality_score: float
    costar_usage_score: float
    creativity_score: float
    feedback: str
    breakdown: dict[str, float]


class RAGASPromptEvaluator:
    """LLM-as-a-judge evaluator for prompt improvements using custom criteria."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        """
        Initialize the LLM-as-a-judge evaluator.

        Args:
            model_name: The OpenAI model to use for evaluation
        """
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=0.1)

        # Custom evaluation criteria
        self.evaluation_prompts = {
            "prompt_quality": """
Evaluate the quality of this improved prompt based on clarity, specificity,
and completeness. Score from 0-5 points.

Original prompt: {original_prompt}
Improved prompt: {improved_prompt}
Context: {context}

Scoring criteria (BE STRICT):
- 5 points: Excellent - Clear, specific, comprehensive, well-structured, addresses all context requirements AND stays on the same topic/domain
- 4 points: Good - Clear and specific with minor gaps, mostly addresses context and stays on topic
- 3 points: Average - Some clarity and specificity, partially addresses context, mostly on topic
- 2 points: Below Average - Vague or incomplete, barely addresses context, somewhat off-topic
- 1 point: Poor - Very vague, confusing, largely irrelevant to context, or wrong topic
- 0 points: No improvement, worse than original, completely different topic, or completely irrelevant

CRITICAL: The improved prompt MUST stay within the same topic/domain as indicated by the context.
- If context is about "academic essay", the improved prompt must be for academic writing, not marketing/business/creative writing
- If context is about "marketing strategy", it must stay in marketing, not switch to academic or technical writing
- If context is about "programming", it must stay technical, not become a creative writing prompt

IMPORTANT: Single words, generic phrases, or prompts that completely change the subject matter automatically get 0-1 points maximum.

You must start your response with "Score: X" where X is the numerical score, then provide reasoning including topic relevance assessment.
""",
            "costar_usage": """
Evaluate how well the improved prompt uses the COSTAR framework elements:
Context, Objective, Style, Tone, Audience, Response format.
Score from 0-3 points.

Original prompt: {original_prompt}
Improved prompt: {improved_prompt}
Context: {context}

Scoring criteria (BE STRICT):
- 3 points: Uses 4+ COSTAR elements effectively and explicitly within the correct topic/domain
- 2 points: Uses 2-3 COSTAR elements clearly and explicitly within the correct topic/domain
- 1 point: Uses 1 COSTAR element clearly within the correct topic/domain
- 0 points: No clear COSTAR elements used OR completely wrong topic/domain

CRITICAL: The improved prompt must stay within the same topic/domain as the context. Even excellent COSTAR usage gets 0 points if it's for the wrong subject matter.
- Academic context → COSTAR elements must be for academic writing
- Marketing context → COSTAR elements must be for marketing
- Programming context → COSTAR elements must be for technical/coding tasks

IMPORTANT: Generic words like "help", "please", single-word responses, or topic-switching automatically get 0 points.

You must start your response with "Score: X" where X is the numerical score, then identify which specific COSTAR elements were used and confirm topic relevance.
""",
            "creativity": """
Evaluate the creativity and innovation in the prompt improvement.
Score from 0-2 points.

Original prompt: {original_prompt}
Improved prompt: {improved_prompt}
Context: {context}

Scoring criteria (BE STRICT):
- 2 points: Highly creative - Novel approach, innovative techniques, creative formatting WITHIN the correct topic/domain
- 1 point: Moderately creative - Some unique elements or approaches WITHIN the correct topic/domain
- 0 points: No creativity, generic, standard, single words, worse than original, OR wrong topic/domain

CRITICAL: Creativity is only valuable if it stays within the correct topic/domain. A brilliantly creative marketing prompt for an academic writing task gets 0 points.

IMPORTANT: Single words, generic phrases like "help" or "please", responses that show no understanding of the task, or topic-switching automatically get 0 points.

You must start your response with "Score: X" where X is the numerical score, then explain the creative elements (or lack thereof) and confirm topic relevance.
""",
        }

        logger.info(f"Initialized LLM evaluator with model: {model_name}")

    async def _evaluate_aspect(
        self, aspect: str, original_prompt: str, improved_prompt: str, context: str
    ) -> tuple[float, str]:
        """
        Evaluate a specific aspect of the prompt improvement.

        Args:
            aspect: The aspect to evaluate ('prompt_quality', 'costar_usage', 'creativity')
            original_prompt: The original bad prompt
            improved_prompt: The user's improved prompt
            context: The context for the prompt scenario

        Returns:
            Tuple of (score, reasoning)
        """
        try:
            evaluation_prompt = self.evaluation_prompts[aspect].format(
                original_prompt=original_prompt,
                improved_prompt=improved_prompt,
                context=context,
            )

            response = await self.llm.ainvoke(evaluation_prompt)
            response_text = response.content

            # Extract score from response (look for number at start or "Score: X")
            score = self._extract_score(response_text, aspect)

            logger.debug(f"Evaluated {aspect}: score={score}")
            return score, response_text

        except Exception as e:
            logger.error(f"Error evaluating {aspect}: {e}")
            return 0.0, f"Error during evaluation: {str(e)}"

    def _extract_score(self, response_text: str, aspect: str) -> float:
        """
        Extract numerical score from evaluation response.

        Args:
            response_text: The LLM's evaluation response
            aspect: The aspect being evaluated

        Returns:
            Extracted score as float
        """
        import re

        # Try to find score patterns
        patterns = [
            r"score[:\s]*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*(?:points?|/)",
            r"^(\d+(?:\.\d+)?)",  # Number at start of line
        ]

        for pattern in patterns:
            match = re.search(pattern, response_text.lower())
            if match:
                try:
                    score = float(match.group(1))
                    # Validate score is within expected range
                    max_scores = {
                        "prompt_quality": 5,
                        "costar_usage": 3,
                        "creativity": 2,
                    }
                    if 0 <= score <= max_scores.get(aspect, 5):
                        return score
                except ValueError:
                    continue

        logger.warning(f"Could not extract score from response for {aspect}")
        return 0.0

    async def evaluate_prompt_improvement(
        self,
        original_prompt: str,
        improved_prompt: str,
        improved_response: str,
        context: str,
    ) -> PromptEvaluation:
        """
        Evaluate a prompt improvement using multiple criteria.

        Args:
            original_prompt: The original bad prompt
            improved_prompt: The user's improved prompt
            improved_response: The LLM response to the improved prompt
            context: The context/scenario for the prompt

        Returns:
            PromptEvaluation with scores and feedback
        """
        logger.info("Starting prompt evaluation")

        try:
            # Evaluate all aspects concurrently
            tasks = [
                self._evaluate_aspect(
                    "prompt_quality", original_prompt, improved_prompt, context
                ),
                self._evaluate_aspect(
                    "costar_usage", original_prompt, improved_prompt, context
                ),
                self._evaluate_aspect(
                    "creativity", original_prompt, improved_prompt, context
                ),
            ]

            results = await asyncio.gather(*tasks)

            prompt_quality_score, prompt_quality_feedback = results[0]
            costar_score, costar_feedback = results[1]
            creativity_score, creativity_feedback = results[2]

            # Calculate total score
            total_score = prompt_quality_score + costar_score + creativity_score

            # Generate comprehensive feedback
            feedback = self._generate_comprehensive_feedback(
                prompt_quality_score,
                prompt_quality_feedback,
                costar_score,
                costar_feedback,
                creativity_score,
                creativity_feedback,
                total_score,
            )

            # Create breakdown
            breakdown = {
                "prompt_quality": prompt_quality_score,
                "costar_usage": costar_score,
                "creativity": creativity_score,
                "total": total_score,
            }

            evaluation = PromptEvaluation(
                total_score=total_score,
                prompt_quality_score=prompt_quality_score,
                costar_usage_score=costar_score,
                creativity_score=creativity_score,
                feedback=feedback,
                breakdown=breakdown,
            )

            log_game_event(
                "prompt_evaluated", {"total_score": total_score, "breakdown": breakdown}
            )

            logger.info(f"Evaluation completed - Total score: {total_score:.2f}/10")
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
        prompt_quality_score: float,
        prompt_quality_feedback: str,
        costar_score: float,
        costar_feedback: str,
        creativity_score: float,
        creativity_feedback: str,
        total_score: float,
    ) -> str:
        """Generate comprehensive feedback from individual evaluations."""

        feedback_parts = [
            f"**🎯 Total Score: {total_score:.1f}/10**",
            "",
            f"**📝 Prompt Quality: {prompt_quality_score:.1f}/5**",
            prompt_quality_feedback,
            "",
            f"**⭐ COSTAR Framework Usage: {costar_score:.1f}/3**",
            costar_feedback,
            "",
            f"**💡 Creativity Bonus: {creativity_score:.1f}/2**",
            creativity_feedback,
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
