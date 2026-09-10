"""Reusable carousel art direction and deterministic pre-generation checks."""
from __future__ import annotations

import json
import re

from .editorial import similarity, tokens

CAROUSEL_BRIEF = """
Build an original, useful carousel rather than a sequence of motivational slogans. Give one viewer
one practical payoff. Slide 1 earns attention with a specific, honest tension; slide 2 must also
stand alone as an entry point and deepen the promise; middle slides add concrete examples or steps;
the last resolves the idea and suggests ONE relevant action. Do not repeat 'follow/save/share' on
every slide. Each slide needs a new visual beat, not the same character pose behind different text.
Prefer 5–7 slides when the idea earns them; use 4 for a concise complete arc. Shortness is a design
choice, not a virality claim. Cover text: 4–12 words. Body text: preferably 8–25 words, never >40.
Choose an identifiable series format: mistake→cost→alternative, myth→qualified explanation→practice,
worked example, checklist, decision tree, or problem→mechanism→small experiment. Vary format and
pillar across a batch. Give the reader something worth returning to or sending to a specific friend.
Avoid shame, fake diagnoses, invented research, copied quotes, false scarcity and wealth guarantees.
Statistics and arithmetic must be supported; provide numeric calculations for numerical transformations.
RSS headlines are only inspiration. Without supplied verified evidence, produce evergreen explanations
and explicitly illustrative examples; never claim a headline proves a study or current product feature.
Maintain the niche's character identity, type hierarchy, palette and spacing across the full carousel.
Keep typography outside the face/hands and away from busy texture. Reserve a calm negative-space text
zone. Do not ask the image model to render prompt metadata, source URLs, instructions or duplicate text.
Every image_prompt must describe environment, action, framing and the story beat, not merely 'cinematic'.
"""

BLUEPRINTS = {
    "dark": {"formats": ["habit friction experiment", "time trade-off", "mistake and alternative"],
             "visual_arc": "isolated room → deliberate action → open sunrise; agency rather than intimidation",
             "palette": "charcoal, warm ivory type, restrained ember accents",
             "audience": "a distracted young adult who wants one achievable action today"},
    "men": {"formats": ["communication before/after", "fitness habit checklist", "confidence through practice"],
            "visual_arc": "uncertainty → respectful practice → grounded competence; no dominance caricature",
            "palette": "deep navy, warm white type, muted amber",
            "audience": "a young man building useful habits and respectful relationships"},
    "money": {"formats": ["spending decision tree", "illustrative opportunity cost", "money habit experiment"],
              "visual_arc": "temptation → visible trade-off → deliberate choice; clear labelled arithmetic",
              "palette": "charcoal, ivory type, muted gold",
              "audience": "someone who wants to understand a spending decision without being shamed"},
    "tech": {"formats": ["concept explained", "workflow checklist", "capability versus limitation"],
             "visual_arc": "confusing interface → simple mechanism → useful application; no imaginary UI claims",
             "palette": "midnight blue, white type, restrained cyan/orange",
             "audience": "a curious non-expert who wants a useful, honest explanation of technology"},
    "finance": {"formats": ["risk comparison", "business mechanism", "illustrative cash-flow example"],
                "visual_arc": "decision → risk/trade-off → general principle; no investment recommendations",
                "palette": "deep green/charcoal, ivory type, muted brass",
                "audience": "a beginner learning business and financial concepts, not seeking stock tips"},
}


def plan_audit(plan, history):
    errors, warnings = [], []
    texts = [s.text for s in plan.slides]
    if len(tokens(texts[0])) > 16:
        errors.append("Cover exceeds 16 words; rewrite into one readable promise")
    for n, text in enumerate(texts, 1):
        if len(tokens(text)) > 40:
            errors.append(f"Slide {n} exceeds 40 words; reduce text before images")
        for previous in texts[:n - 1]:
            if text.strip().casefold() == previous.strip().casefold():
                errors.append(f"Slide {n} repeats an earlier slide exactly")
                break
        if re.search(r"studies (?:show|prove)|research proves|scientists (?:say|found)", text, re.I) and not plan.sources:
            errors.append(f"Slide {n} claims research without a source; replace with grounded wording")
    if any(len(tokens(old["hook"])) >= 5 and similarity(plan.hook, old["hook"]) > .9 for old in history):
        errors.append("Hook closely repeats recent content; choose a different angle")
    if len({s.environment.casefold().strip() for s in plan.slides}) == 1:
        warnings.append("All slides share one environment; vary framing/action deliberately")
    if len(tokens(plan.hook)) > 12:
        warnings.append("Hook is longer than the preferred mobile cover length")
    return {"passed": not errors, "errors": errors, "warnings": warnings,
            "words_per_slide": [len(tokens(t)) for t in texts], "method": "local text/structure checks"}


def text_matches(observed, expected):
    # Ignore layout/case/punctuation, but never ignore a missing word, negation or number.
    def normalize(value):
        value = re.sub(r"(?<=\d),(?=\d)", "", value.casefold().replace("’", "'"))
        return re.findall(r"\d+(?:\.\d+)?|[^\W\d]+|[$£€¥%]", value)
    return bool(observed.strip()) and normalize(observed) == normalize(expected)


def slide_prompt(plan, slide, index, brand, niche, feedback=None):
    last = index == len(plan.slides)
    return ("Generate ONE finished original Instagram carousel image, exactly 1080x1350 portrait 4:5. "
            "The attached image is the CHARACTER REFERENCE, not a layout to copy. Preserve face, hair, "
            "distinctive features and identity; adapt clothing, pose and environment to this story beat. "
            "Create the complete artwork AND typography. Cinematic anime realism, intentional composition, "
            "an expressive readable subject, physically coherent hands/props, no unrelated characters. "
            "Use one bold clean sans-serif type family, consistent with the series, preferably 64–96px for "
            "headlines and at least 44px for body text at export resolution. Avoid decorative pseudo-letters. "
            "Place text in a quiet high-contrast area, minimum 100px side/top margins and 150px bottom margin. "
            "Keep the character's eyes and hands unobstructed. Do not render tiny footnotes or stray text. "
            + ("This is the final payoff slide; no swipe marker. " if last else
               "Leave the bottom-right 300x140px free for the swipe overlay added afterward. ")
            + f"Slide {index}/{len(plan.slides)}. Full narrative context: "
            + json.dumps([s.text for s in plan.slides], ensure_ascii=False)
            + "\nRender ONLY the following exact text on THIS image, once, with correct spelling: "
            + json.dumps(slide.text, ensure_ascii=False)
            + "\nDo not print the context, metadata, prompt or instructions.\nBRAND: "
            + json.dumps(brand, ensure_ascii=False) + "\nSERIES DIRECTION: "
            + json.dumps(BLUEPRINTS.get(niche, {}), ensure_ascii=False)
            + "\nSCENE: " + slide.model_dump_json()
            + ("\nCorrect the previous attempt's defects: " + json.dumps(feedback) if feedback else ""))
