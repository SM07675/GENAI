"""Multimodal Context Fusion for Genie OS.

Fuses voice, screen, application, files, project, memory, and environment
into a high-signal unified context with relevance scoring.

The AI planner/orchestrator receives only relevant context rather than
dumping every available piece of raw context into the prompt.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger("genie.context.fusion")

# Common stop words for keyword extraction
_STOP_WORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "genie", "hey", "please", "okay",
})


def _extract_keywords(text: str) -> set[str]:
    """Extract significant keywords from a text query."""
    if not text:
        return set()
    tokens = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS}


@dataclass
class ScoredContextItem:
    """A context item with a relevance score (0.0 to 1.0)."""
    category: str      # "app" | "screen" | "file" | "project" | "memory" | "preference" | "clipboard"
    title: str
    content: str
    relevance: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FusedContext:
    """The fused context output from the Context Fusion layer."""
    query: str
    active_app: str
    active_window: str
    app_category: str
    relevant_items: List[ScoredContextItem] = field(default_factory=list)
    system_summary: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_prompt_block(self, max_items: int = 8, min_relevance: float = 0.25) -> str:
        """Format the most relevant context items for LLM injection."""
        sorted_items = sorted(
            [it for it in self.relevant_items if it.relevance >= min_relevance],
            key=lambda x: x.relevance,
            reverse=True,
        )[:max_items]

        lines = [
            f"=== CONTEXT SNAPSHOT ===",
            f"Active Application: {self.active_app} ({self.app_category})",
            f"Active Window: {self.active_window}",
        ]

        if sorted_items:
            lines.append("Relevant Context:")
            for item in sorted_items:
                lines.append(f"- [{item.category.upper()}] {item.title}: {item.content}")

        return "\n".join(lines)


class ContextFusion:
    """Fuses multimodal context streams and ranks by relevance."""

    @staticmethod
    def score_item(item_text: str, query_keywords: set[str], default_score: float = 0.4) -> float:
        """Score an item against query keywords."""
        if not query_keywords:
            return default_score
        item_keywords = _extract_keywords(item_text)
        if not item_keywords:
            return default_score
        overlap = query_keywords & item_keywords
        ratio = len(overlap) / max(1, len(query_keywords))
        return min(1.0, default_score + (ratio * 0.6))

    def fuse(
        self,
        query: str,
        app_state: Dict[str, Any],
        screen_context: Optional[Dict[str, Any]] = None,
        memories: Optional[List[Dict[str, Any]]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        projects: Optional[List[Dict[str, Any]]] = None,
        files: Optional[List[Dict[str, Any]]] = None,
        clipboard: Optional[str] = None,
    ) -> FusedContext:
        """Fuse and score all available context sources."""
        query_keywords = _extract_keywords(query)
        scored_items: List[ScoredContextItem] = []

        active_app = app_state.get("process_name", app_state.get("active_app", "Desktop"))
        active_window = app_state.get("window_title", app_state.get("active_window", "Workspace"))
        app_category = app_state.get("category", "general")

        # 1. Screen / Visual context
        if screen_context:
            summary = screen_context.get("summary") or screen_context.get("description") or ""
            if summary:
                score = self.score_item(summary, query_keywords, default_score=0.6)
                scored_items.append(ScoredContextItem(
                    category="screen",
                    title="Screen View",
                    content=summary[:300],
                    relevance=score,
                    metadata=screen_context,
                ))

        # 2. Clipboard context
        if clipboard and len(clipboard.strip()) > 0:
            clip_preview = clipboard.strip()[:200]
            score = self.score_item(clip_preview, query_keywords, default_score=0.45)
            scored_items.append(ScoredContextItem(
                category="clipboard",
                title="Clipboard",
                content=clip_preview,
                relevance=score,
            ))

        # 3. Memories
        if memories:
            for mem in memories:
                content = mem.get("content") or mem.get("value") or ""
                key = mem.get("key") or mem.get("tags") or "Memory"
                if content:
                    score = self.score_item(f"{key} {content}", query_keywords, default_score=0.5)
                    scored_items.append(ScoredContextItem(
                        category="memory",
                        title=str(key),
                        content=str(content)[:250],
                        relevance=score,
                        metadata=mem,
                    ))

        # 4. Preferences
        if preferences:
            for k, v in preferences.items():
                score = self.score_item(f"{k} {v}", query_keywords, default_score=0.35)
                scored_items.append(ScoredContextItem(
                    category="preference",
                    title=str(k),
                    content=str(v),
                    relevance=score,
                ))

        # 5. Projects
        if projects:
            for prj in projects:
                name = prj.get("name", "Project")
                desc = prj.get("description", "")
                tech = ", ".join(prj.get("technology", []))
                text = f"{name} {desc} {tech}"
                score = self.score_item(text, query_keywords, default_score=0.5)
                scored_items.append(ScoredContextItem(
                    category="project",
                    title=str(name),
                    content=f"{desc} (Tech: {tech})" if tech else desc,
                    relevance=score,
                    metadata=prj,
                ))

        # 6. Files
        if files:
            for f in files:
                fname = f.get("name") or f.get("path") or "File"
                fsummary = f.get("summary", "")
                score = self.score_item(f"{fname} {fsummary}", query_keywords, default_score=0.5)
                scored_items.append(ScoredContextItem(
                    category="file",
                    title=str(fname),
                    content=str(fsummary)[:200],
                    relevance=score,
                    metadata=f,
                ))

        return FusedContext(
            query=query,
            active_app=active_app,
            active_window=active_window,
            app_category=app_category,
            relevant_items=scored_items,
        )


context_fusion = ContextFusion()
