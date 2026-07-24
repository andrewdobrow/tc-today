"""
Treasure Coast Today editorial engine.

This package contains the isolated, tested editorial intelligence that will
eventually replace duplicated decision logic inside the production engine.
"""

from .activation import (
    ACTIVATION_VERSION,
    DEFAULT_MAX_ACTIONS,
    ActivationAction,
    ActivationConfig,
    ActivationPreflight,
    ActivationRecommendation,
    ActivationRun,
    EngineMode,
    apply_activation_to_categories,
    build_activation_preflight,
    build_activation_run,
    extend_activation_run_with_guarded_suppressions,
    recommend_activation_action,
    recommendation_from_guarded_suppression,
    trip_activation_circuit_breaker,
)
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
from .incident_identity import (
    INCIDENT_IDENTITY_VERSION,
    IncidentIdentityMatch,
    IncidentSignature,
    build_incident_signature,
    build_story_incident_signature,
    compare_incident_signatures,
    compare_story_incidents,
    find_matching_incident_story,
)
from .source_identity import (
    SOURCE_IDENTITY_VERSION,
    SourceIdentityMatch,
    find_matching_source_story,
    normalize_source_identity_url,
    story_source_identity_urls,
)
from .rss_adapter import (
    RSSArticleAdapter,
    RSSArticleError,
)
from .editorial_engine import (
    EditorialEngine,
    EditorialEngineResult,
    EditorialStateError,
)
from .editorial_proximity import (
    EditorialProximity,
    EditorialScore,
    calculate_editorial_priority,
    calculate_editorial_score,
    classify_editorial_proximity,
    latest_story_timestamp,
    story_source_trust,
)
from .local_relevance import LocalRelevance, classify_local_relevance
from .story_lifecycle import (
    StoryLifecycle,
    StoryLifecycleState,
    classify_story_lifecycle,
)
from .registry_repair import (
    REPAIR_VERSION,
    RegistryRepairReport,
    is_sparse_event_key,
    normalize_identity_title,
    normalize_title,
    strip_publisher_suffix,
    repair_registry_payload,
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
    "ACTIVATION_VERSION",
    "DEFAULT_MAX_ACTIONS",
    "ActivationAction",
    "ActivationConfig",
    "ActivationPreflight",
    "ActivationRecommendation",
    "ActivationRun",
    "EngineMode",
    "apply_activation_to_categories",
    "build_activation_preflight",
    "build_activation_run",
    "extend_activation_run_with_guarded_suppressions",
    "recommend_activation_action",
    "recommendation_from_guarded_suppression",
    "trip_activation_circuit_breaker",
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
    "INCIDENT_IDENTITY_VERSION",
    "IncidentIdentityMatch",
    "IncidentSignature",
    "build_incident_signature",
    "build_story_incident_signature",
    "compare_incident_signatures",
    "compare_story_incidents",
    "find_matching_incident_story",
    "SOURCE_IDENTITY_VERSION",
    "SourceIdentityMatch",
    "find_matching_source_story",
    "normalize_source_identity_url",
    "story_source_identity_urls",
    "RSSArticleAdapter",
    "RSSArticleError",
    "EditorialEngine",
    "EditorialEngineResult",
    "EditorialStateError",
    "ENGINE_NAME",
    "ENGINE_VERSION",
    "ENGINE_RELEASE",
    "EditorialProximity",
    "EditorialScore",
    "classify_editorial_proximity",
    "calculate_editorial_priority",
    "calculate_editorial_score",
    "latest_story_timestamp",
    "story_source_trust",
    "StoryLifecycle",
    "StoryLifecycleState",
    "classify_story_lifecycle",
    "REPAIR_VERSION",
    "RegistryRepairReport",
    "is_sparse_event_key",
    "normalize_identity_title",
    "normalize_title",
    "strip_publisher_suffix",
    "repair_registry_payload",
    "OBSERVABILITY_SCHEMA_VERSION",
    "build_editorial_observability",
    "write_editorial_observability",
    "ProductionInstruction",
    "ProductionRoute",
    "route_editorial_result",
]

__version__ = "1.9.2"
