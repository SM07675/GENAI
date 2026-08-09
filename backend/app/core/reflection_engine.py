"""
Reflection Engine for Genie OS.

Evaluates plan confidence score before tool execution and returns clarification
requests or uncertainty flags for ambiguous/low-confidence intentions.
"""
import logging
from typing import Any, Dict, List, Tuple

log = logging.getLogger("genie_os.reflection")

CONFIDENCE_THRESHOLD = 0.65


class ReflectionEngine:
    """Evaluates plan confidence and prevents unverified/ambiguous tool execution."""

    def evaluate_plan(
        self,
        user_query: str,
        proposed_tools: List[Dict[str, Any]],
        context_summary: str = ""
    ) -> Tuple[float, bool, str]:
        """Evaluates proposed plan confidence.

        Returns:
            Tuple[confidence_score (0.0-1.0), is_acceptable (bool), explanation/clarification_question]
        """
        if not proposed_tools:
            return 1.0, True, "Direct conversational turn."

        query_lower = user_query.lower()
        score = 0.95  # Base confidence

        # Check for vague target references in destructive/write commands
        for tool in proposed_tools:
            tool_name = tool.get("name", "")
            args = tool.get("args", {})
            args_str = str(args).lower()

            # Ambiguous references like "that file", "it", "them" without specific path/target
            if any(term in query_lower for term in ["delete it", "remove them", "clear that", "close everything"]):
                if not args or "all" in args_str:
                    score -= 0.40

            # Missing required arguments or empty params
            if not args and tool_name not in ["get_screen_summary", "list_open_apps"]:
                score -= 0.35

        is_acceptable = score >= CONFIDENCE_THRESHOLD

        if not is_acceptable:
            clarification = (
                f"I want to make sure I get this right. Could you clarify which target you'd like me to run "
                f"'{proposed_tools[0].get('name', 'this tool')}' on?"
            )
            log.warning(f"Low plan confidence ({score:.2f}) for query '{user_query}'. Requesting clarification.")
            return score, False, clarification

        return score, True, "Plan passed reflection evaluation."


reflection_engine = ReflectionEngine()
