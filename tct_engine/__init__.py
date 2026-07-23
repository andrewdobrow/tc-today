"""
Treasure Coast Today editorial engine.

This package contains the isolated, tested editorial intelligence that will
eventually replace duplicated decision logic inside the production engine.
"""

from .editorial_policy import EditorialPolicy, SourceProfile
from .editorial_eligibility import (
    EditorialEligibilityEngine,
    EligibilityDecision,
    EligibilityStatus,
)
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
from .story_importance import (
    ImportanceLevel,
    ImportanceReason,
    StoryImportance,
    StoryImportanceEngine,
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
from .observability import (
    ENGINE_NAME,
    ENGINE_VERSION,
    ENGINE_RELEASE,
    OBSERVABILITY_SCHEMA_VERSION,
    build_editorial_observability,
    write_editorial_observability,
)
from .production_router import (
    ProductionInstruction,
    ProductionRoute,
    route_editorial_result,
)

__all__ = [
    "EditorialPolicy",
    "SourceProfile",
    "EditorialEligibilityEngine",
    "EligibilityDecision",
    "EligibilityStatus",
    "ArticleIdentityInput",
    "EventIdentity",
    "resolve_event_identity",
    "CanonicalStory",
    "CanonicalStoryManager",
    "StoryCandidate",
    "select_canonical_story",
    "ImportanceLevel",
    "ImportanceReason",
    "StoryImportance",
    "StoryImportanceEngine",
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
    "ENGINE_NAME",
    "ENGINE_VERSION",
    "ENGINE_RELEASE",
    "OBSERVABILITY_SCHEMA_VERSION",
    "build_editorial_observability",
    "write_editorial_observability",
    "ProductionInstruction",
    "ProductionRoute",
    "route_editorial_result",
]

__version__ = "1.5.0"
from .local_relevance import LocalRelevance, classify_local_relevance
