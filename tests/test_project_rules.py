import pytest
from pydantic import ValidationError

from cliper.captions import write_captions
from cliper.media import filter_graph
from cliper.models import Preferences
from cliper.project_rules import apply, description
from cliper.publishing import caption_text
from cliper.speed_profile import instructions, preset


def test_required_description_survives_limits_and_repeated_application(clip):
    prefs = Preferences(description_suffix="Follow for more. #done #Football")
    clip.caption = "a" * 1800
    clip.hashtags = ["one", "two", "three", "four", "five"]
    output = apply(clip, prefs)
    assert output.hashtags == ["done", "Football", "one", "two", "three"]
    assert len(output.caption) <= 1800
    assert output.caption.endswith("Follow for more.")
    assert apply(output, prefs) == output
    assert "#done" in caption_text(output.caption, output.hashtags)
    assert "Follow for more." not in clip.caption


def test_rules_do_not_leak_and_guidance_reaches_both_profiles():
    rule = "Focus on football reactions and use playful hooks."
    prefs = Preferences(project_rules=rule)
    assert rule in instructions(prefs)
    assert rule in instructions(preset(prefs))
    assert rule not in instructions(Preferences())
    assert description("A story", ["old"], Preferences()) == ("A story", ["old"])
    with pytest.raises(ValidationError):
        Preferences(description_suffix="#one #two #three #four #five #six")


def test_overlay_is_separate_from_speech_and_renders_without_subtitles(tmp_path, transcript, clip):
    prefs = Preferences(overlay_text=r"#done {\pos(0,0)}", captions=False, layout="legacy")
    path = write_captions(tmp_path, transcript, clip, prefs)
    ass = path.read_text("utf-8-sig")
    assert "Dialogue: 2,0:00:00.00,0:00:19.00" in ass
    assert "#done (／pos(0,0))" in ass
    assert path.with_suffix(".srt").read_text() == ""
    graph, _ = filter_graph(prefs, None, path.name)
    assert "ass=filename=" in graph
