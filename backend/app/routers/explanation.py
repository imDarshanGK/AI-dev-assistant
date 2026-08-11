"""Explanation router — POST /explanation/."""

import time

from fastapi import APIRouter

from ..schemas import CodeRequest, ExplanationResponse
from ..services.code_assistant import detect_language, run_explanation
from ..services.llm_analysis import LLMAnalysisError, llm_analysis_client

router = APIRouter()


@router.post(
    "/",
    response_model=ExplanationResponse,
    summary="Explain code using AI with rule-based fallback",
)
async def explain(req: CodeRequest):
    start = time.perf_counter()

    lang = detect_language(req.code, req.language)

    # Keep the existing rule-based explanation as a reliable fallback.
    fallback = run_explanation(req.code, lang)

    # Use the LLM when it is enabled.
    if llm_analysis_client.enabled:
        try:
            ai_result = await llm_analysis_client.analyze_code_structured(
                req.code,
                lang,
            )

            # The LLM response may contain the explanation inside
            # an "explanation" object or directly at the top level.
            ai_explanation = ai_result.get(
                "explanation",
                ai_result,
            )

            if isinstance(ai_explanation, dict):
                if ai_explanation.get("summary"):
                    fallback["summary"] = ai_explanation["summary"]
                    fallback["overview"] = ai_explanation["summary"]

                    # Use the LLM summary as the purpose when the
                    # structured LLM response does not provide a purpose.
                    if not ai_explanation.get("purpose"):
                        fallback["purpose"] = ai_explanation["summary"]

                if ai_explanation.get("key_points"):
                    fallback["key_points"] = ai_explanation["key_points"]

                if ai_explanation.get("purpose"):
                    fallback["purpose"] = ai_explanation["purpose"]

                if ai_explanation.get("overview"):
                    fallback["overview"] = ai_explanation["overview"]

                if ai_explanation.get("step_by_step"):
                    fallback["step_by_step"] = ai_explanation["step_by_step"]

                if ai_explanation.get("line_by_line"):
                    fallback["line_by_line"] = ai_explanation["line_by_line"]

                if ai_explanation.get("inputs"):
                    fallback["inputs"] = ai_explanation["inputs"]

                if ai_explanation.get("outputs"):
                    fallback["outputs"] = ai_explanation["outputs"]

                if ai_explanation.get("algorithm"):
                    fallback["algorithm"] = ai_explanation["algorithm"]

                if ai_explanation.get("time_complexity"):
                    fallback["time_complexity"] = ai_explanation[
                        "time_complexity"
                    ]

                if ai_explanation.get("space_complexity"):
                    fallback["space_complexity"] = ai_explanation[
                        "space_complexity"
                    ]

                if ai_explanation.get("best_practices"):
                    fallback["best_practices"] = ai_explanation[
                        "best_practices"
                    ]

                if ai_explanation.get("optimizations"):
                    fallback["optimizations"] = ai_explanation[
                        "optimizations"
                    ]

                if ai_explanation.get("common_mistakes"):
                    fallback["common_mistakes"] = ai_explanation[
                        "common_mistakes"
                    ]

                if ai_explanation.get("real_world_applications"):
                    fallback["real_world_applications"] = ai_explanation[
                        "real_world_applications"
                    ]

                if ai_explanation.get("beginner_tip"):
                    fallback["beginner_tip"] = ai_explanation[
                        "beginner_tip"
                    ]

            # Support the current LLM response format:
            # {"complexity": {"time": "...", "space": "..."}}
            complexity = ai_result.get("complexity", {})

            if isinstance(complexity, dict):
                if complexity.get("time"):
                    fallback["time_complexity"] = complexity["time"]

                if complexity.get("space"):
                    fallback["space_complexity"] = complexity["space"]

            # Mark the actual provider used.
            fallback["provider"] = "llm"
            fallback["model"] = llm_analysis_client.model

            fallback["analysis_time_ms"] = round(
                (time.perf_counter() - start) * 1000,
                2,
            )

            return fallback

        except LLMAnalysisError:
            # If the LLM fails, safely use the existing rule-based result.
            pass

    # LLM disabled/unavailable → existing rule-based behaviour.
    fallback["provider"] = "rule-based"
    fallback["model"] = "qyverix-engine-v3"
    fallback["analysis_time_ms"] = round(
        (time.perf_counter() - start) * 1000,
        2,
    )

    return fallback
