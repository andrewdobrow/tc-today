import json
import sys
import types
from pathlib import Path

if "feedparser" not in sys.modules:
    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = feedparser
if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class _Anthropic:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

    anthropic.Anthropic = _Anthropic
    sys.modules["anthropic"] = anthropic
if "json_repair" not in sys.modules:
    json_repair = types.ModuleType("json_repair")
    json_repair.repair_json = lambda value: value
    sys.modules["json_repair"] = json_repair

from scripts import generate


class _Block:
    def __init__(self, text):
        self.text = text


class _Response:
    def __init__(self, payload, model="claude-sonnet-5"):
        self.content = [_Block(json.dumps(payload))]
        self.model = model


class _QueueMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("No fake response queued")
        return self.responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.messages = _QueueMessages(responses)

    def with_options(self, **kwargs):
        return self


def _packet():
    return {
        "category_key": "crime",
        "category_label": "Crime & Safety",
        "source_inputs": [
            {
                "source_index": 1,
                "title": "Detectives continue Rondon investigation",
                "published": "Fri, 02 Oct 2026 21:00:00 -0400",
                "source_type": "publisher",
                "source_quality": "full",
                "hero_eligible": True,
                "category_match_score": 10,
                "story_form": "new",
                "article_text": (
                    "The Martin County Sheriff's Office said detectives continue the investigation. "
                    "Additional charges against Rondon are possible as detectives review video and "
                    "search warrants involving phones and vehicles."
                ),
                "canonical_context_headline": "",
                "canonical_context_body": "",
            }
        ],
    }


def test_copydesk_detects_repeated_and_chain_from_live_regression():
    sentence = (
        "The Martin County Sheriff's Office says additional charges against Rondon are likely "
        "as detectives continue reviewing video and phone and vehicle search warrants."
    )
    issues = generate._copydesk_text_issues(sentence)
    assert "chained_and" in {issue["code"] for issue in issues}


def test_copydesk_accepts_normal_journalistic_list_construction():
    sentence = (
        "Detectives are reviewing video, phone records and vehicle search warrants as the investigation continues."
    )
    assert generate._copydesk_text_issues(sentence) == []


def test_copydesk_enforces_no_em_dashes():
    issues = generate._copydesk_text_issues(
        "Deputies returned Friday — two days after the initial search."
    )
    assert "em_dash" in {issue["code"] for issue in issues}


def test_copydesk_does_not_rewrite_a_quoted_and_chain_by_rule_alone():
    text = 'The sheriff said, “We checked the house and the car and the shed.” Investigators returned Friday.'
    assert generate._copydesk_text_issues(text) == []


def test_newsroom_standard_requires_publish_ready_grammar_style_and_no_em_dash():
    standard = generate.NEWSROOM_COPY_DESK_STANDARD
    assert "publication-ready local journalism" in standard
    assert "grammar" in standard
    assert "parallel construction" in standard
    assert "engaging" in standard
    assert "Never use an em dash" in standard
    assert "Do not chain repeated conjunctions" in standard
    assert generate.CATEGORY_GENERATION_PROMPT_VERSION == "v1.13.9.81-newsroom-copy-desk"


def test_assignment_writer_runs_bounded_copydesk_repair_for_and_chain(monkeypatch):
    bad = _Response({
        "headline": "Detectives continue Rondon investigation",
        "body": (
            "The Martin County Sheriff's Office says additional charges against Rondon are likely "
            "as detectives continue reviewing video and phone and vehicle search warrants.\n\n"
            "The investigation remains active."
        ),
        "urgency_score": 6,
        "published": "wrong",
        "source_index": 99,
    })
    repaired = _Response({
        "headline": "Detectives continue Rondon investigation",
        "body": (
            "The Martin County Sheriff's Office says additional charges against Rondon are likely "
            "as detectives continue reviewing video and search warrants involving phones and vehicles.\n\n"
            "The investigation remains active."
        ),
    })
    fake = _FakeClient([bad, repaired])
    monkeypatch.setattr(generate, "client", fake)

    item, _model, _duration = generate._run_assignment_writer(
        _packet(),
        {"source_index": 1, "angle": "Lead with the continuing investigation", "urgency_score": 6},
        role="hero",
    )

    assert len(fake.messages.calls) == 2
    assert "final copy desk" in fake.messages.calls[1]["messages"][0]["content"]
    assert "phone and vehicle search warrants" not in item["body"]
    assert generate._article_copydesk_diagnostics(item)["passed"] is True
    assert item["source_index"] == 1
    assert item["urgency_score"] == 6
    assert item["published"] == "Fri, 02 Oct 2026 21:00:00 -0400"


def test_final_generation_boundary_references_copydesk_integrity_gate():
    source = Path("scripts/generate.py").read_text()
    assert "Final generated-copy house-style gate" in source
    assert "Copy-desk integrity failed for hero" in source
    assert 'return "copydesk_integrity"' in source
