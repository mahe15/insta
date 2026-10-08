import re

from cliper.captions import chunks, write_captions
from cliper.edit_layout import fit_text, layout
from cliper.media import filter_graph
from cliper.models import Preferences, Segment, Transcript, Word


def test_hook_follows_visible_frame_not_square_container(tmp_path, transcript, clip):
    prefs = Preferences(preserve_wide_groups=True)
    wide = layout(prefs, {"width": 1920, "height": 1080, "square_mode": "fit"})
    square = layout(prefs, {"width": 1080, "height": 1080})
    assert wide["video_y"] > square["video_y"]
    assert wide["video_y"] - wide["hook_bottom"] == 27
    assert wide["caption_bottom"] < wide["video_y"] + wide["video_height"]
    ass = write_captions(tmp_path, transcript, clip, prefs, wide).read_text("utf-8-sig")
    assert f"\\pos(540,{wide['hook_bottom']})" in ass
    assert f"\\pos(540,{wide['caption_bottom']})" in ass


def test_overlap_and_equal_word_times_preserve_text_without_invalid_cues(clip):
    source = Transcript(language="en", duration=3, segments=[Segment(start=0, end=3, text="One two three",
        words=[Word(start=0, end=1.2, text="One"), Word(start=0, end=1.2, text="two"), Word(start=.8, end=2, text="three")])])
    words = [w for group in chunks(source, clip) for w in group]
    assert " ".join(w.text for w in words) == "One two three"
    assert all(a.end <= b.start for a, b in zip(words, words[1:], strict=False))
    assert all(w.start < w.end for w in words)


def test_long_romanized_caption_is_wrapped_without_dropping_characters():
    text = "Yeh galti karne se pehle ek baar sochna zaroori hai"
    lines, size = fit_text(text, 880, 68, 32)
    assert len(lines) <= 2 and " ".join(lines) == text
    assert 32 <= size <= 68


def test_grading_and_zoom_happen_before_canvas_and_text():
    graph, _ = filter_graph(Preferences(), {"width": 1920, "height": 1080}, "x.ass",
                            zoom=[{"start": 1, "end": 1.65}])
    assert graph.index("eq=") < graph.index("[graded];") < graph.index("pad=") < graph.index("ass=")
    assert "fps=60" in graph and "pow(sin" in graph and "flags=lanczos" in graph
    assert "tonemap=" in filter_graph(Preferences(), {}, "x.ass", hdr=True)[0]


def test_caption_events_never_reverse_after_clipping(tmp_path, clip):
    source = Transcript(language="en", duration=3, segments=[Segment(start=0, end=3, text="One two",
        words=[Word(start=0, end=1.2, text="One"), Word(start=.8, end=2, text="two")])])
    ass = write_captions(tmp_path, source, clip.model_copy(update={"start": .5, "end": 2}), Preferences()).read_text("utf-8-sig")
    for start, end in re.findall(r"Dialogue: \d,([^,]+),([^,]+),", ass):
        assert start < end
