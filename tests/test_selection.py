import pytest
from pydantic import ValidationError

from cliper.models import Preferences, Proposal, Ratings, Transcript
from cliper.selection import deduplicate, heuristic, select, validate_proposals, windows


def proposal(first=0, last=3, hook="invented hook"):
    return Proposal(first_segment=first, last_segment=last, title="A useful lesson", reason="Setup and payoff",
                    hook_text=hook, ratings=Ratings(hook=80, payoff=80, standalone=80, emotion=70, usefulness=85))


def test_reject_out_of_range_and_length(transcript):
    prefs = Preferences(min_seconds=15, max_seconds=25)
    result = validate_proposals([proposal(last=999), proposal(last=0), proposal(first=4, last=3),
                                 proposal()], transcript, prefs, "test")
    assert len(result) == 1
    assert (result[0].start, result[0].end) == (0, 19)
    assert result[0].hook_text == transcript.segments[0].text


def test_dedup_removes_overlapping_and_repeated_text(clip):
    overlap = clip.model_copy(update={"start": 10, "end": 30, "score": 70})
    repeated = clip.model_copy(update={"start": 80, "end": 99, "score": 60})
    distinct = clip.model_copy(update={"start": 100, "end": 119, "text": "Gardening soil roots water tomato", "score": 65})
    result = deduplicate([overlap, repeated, distinct, clip], 5)
    assert [c.start for c in result] == [0, 100]
    assert [c.id for c in result] == [1, 2]


def test_offline_ranking_is_bounded_and_labelled(transcript):
    result = heuristic(transcript, Preferences(clips=3, min_seconds=15, max_seconds=25))
    assert result
    assert all(c.selection_method == "heuristic" and c.score < 70 for c in result)
    assert all(15 <= c.end - c.start <= 25 for c in result)


def test_all_transcript_sections_covered(transcript):
    result = windows(transcript, max_chars=100)
    assert set().union(*(set(w) for w in result)) == set(range(len(transcript.segments)))
    assert len(result) <= len(transcript.segments)


def test_timestamp_and_settings_validation(transcript):
    bad = transcript.model_dump()
    bad["segments"][1]["start"] = -1
    with pytest.raises(ValidationError):
        Transcript.model_validate(bad)
    with pytest.raises(ValidationError):
        Preferences(min_seconds=60, max_seconds=30)
    with pytest.raises(ValidationError):
        Ratings(hook=float("nan"), payoff=0, standalone=0, emotion=0, usefulness=0)


async def test_empty_transcript_is_actionable(cfg):
    async def progress(text):
        pass
    with pytest.raises(ValueError, match="No speech"):
        await select(Transcript(language="en", duration=10, segments=[]), Preferences(), cfg, progress)


async def test_openai_context_candidates_and_critique(monkeypatch, cfg, transcript):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import openai

    from cliper.models import Proposals

    response = SimpleNamespace(status="completed", output_parsed=Proposals(clips=[proposal()]))
    client = SimpleNamespace(responses=SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(status="completed", output_text="Project failure lesson.")),
        parse=AsyncMock(return_value=response)))

    class FakeClient:
        async def __aenter__(self):
            return client

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: FakeClient())
    cfg.provider, cfg.api_key = "openai", "test-only"
    stages = []

    async def progress(text):
        stages.append(text)

    result = await select(transcript, Preferences(min_seconds=15, max_seconds=25), cfg, progress)
    assert result.clips[0].start == 0
    assert result.method == "openai"
    assert client.responses.create.await_count == 1
    assert client.responses.parse.await_count == 2
    assert all(call.kwargs["store"] is False for call in client.responses.parse.await_args_list)
    assert "Reviewing context" in stages[-1]

