"""
Treasure Coast Today editorial engine.

This package contains the isolated, tested editorial intelligence that will
eventually replace duplicated decision logic inside the production engine.
"""

from .event_identity import (
    ArticleIdentityInput,
    EventIdentity,
    resolve_event_identity,
)
from .canonical_story import (
    CanonicalStory,
    CanonicalStoryManager,
    StoryCandidate,
    select_canonical_story,
)
from .story_evolution import (
    IncomingStoryUpdate,
    StorySnapshot,
    StoryUpdateResult,
    UpdateClassification,
    evaluate_story_update,
)
from .editorial_decision import (
    EditorialAction,
    EditorialDecision,
    EditorialDecisionInput,
    decide_editorial_action,
)
from .editorial_pipeline import (
    EditorialPipeline,
    EditorialPipelineResult,
    PipelineArticle,
)
from .fact_extraction import (
    RawArticle,
    ExtractedArticleFacts,
    extract_article_facts,
)
from .event_key import generate_event_key
from .rss_adapter import (
    RSSArticleAdapter,
    RSSArticleError,
)
from .editorial_engine import (
    EditorialEngine,
    EditorialEngineResult,
    EditorialStateError,
)
from .production_router import (
    ProductionInstruction,
    ProductionRoute,
    route_editorial_result,
)

__all__ = [
    "ArticleIdentityInput",
    "EventIdentity",
    "resolve_event_identity",
    "CanonicalStory",
    "CanonicalStoryManager",
    "StoryCandidate",
    "select_canonical_story",
    "IncomingStoryUpdate",
    "StorySnapshot",
    "StoryUpdateResult",
    "UpdateClassification",
    "evaluate_story_update",
    "EditorialAction",
    "EditorialDecision",
    "EditorialDecisionInput",
    "decide_editorial_action",
    "EditorialPipeline",
    "EditorialPipelineResult",
    "PipelineArticle",
    "RawArticle",
    "ExtractedArticleFacts",
    "extract_article_facts",
    "generate_event_key",
    "RSSArticleAdapter",
    "RSSArticleError",
    "EditorialEngine",
    "EditorialEngineResult",
    "EditorialStateError",
    "ProductionInstruction",
    "ProductionRoute",
    "route_editorial_result",
]

__version__ = "0.1.0"