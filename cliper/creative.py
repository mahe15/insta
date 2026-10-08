"""Reusable carousel art direction and deterministic pre-generation checks."""
from __future__ import annotations

import json
import re

from .editorial import similarity, tokens

CAROUSEL_BRIEF = """
Build an original, high-impact Instagram carousel following these 10 core design rules:

1. FONT & TYPOGRAPHY:
Use a bold, modern sans-serif font with a thick/heavy weight similar to Montserrat ExtraBold, Anton, or Bebas Neue.
Font must be clean, simple and highly readable on a phone.
STRICTLY NEVER use decorative, cursive, thin, script, or handwritten fonts.

2. FONT SIZE:
Text must be large, punchy and dominant on the slide.
Main headline / primary numbers: approximately 8–12% of image height (108–162px on 1080x1350).
Secondary text: approximately 6–9% of image height (80–120px).
Never make text small just to fit more words. If the sentence doesn't fit, shorten the sentence instead of reducing font size.

3. TEXT COLOUR:
Strict primary text palette:
- Main text: solid crisp WHITE.
- Important numbers / key impact keywords: vibrant bold RED.
Use only these primary text colours. Example: "20 PUSH-UPS" in RED, "PER DAY" in WHITE.
Maintain strong contrast against the background at all times.

4. TEXT LENGTH:
Very little text. Prefer 1 single line; maximum 2 short lines.
NEVER use paragraphs or blocks of text on the image.
Target approximately 3–8 words per slide.
The image must communicate the story, not a block of text.

5. DAILY → YEARLY COMPARISON:
Every applicable post should create a clear small daily action → huge yearly result comparison.
Always calculate the number correctly (e.g. 10 PAGES A DAY → 3,650 PAGES A YEAR; 50 PUSH-UPS A DAY → 18,250 PUSH-UPS A YEAR; 30 MINUTES A DAY → 182.5 HOURS A YEAR).
Make the compound yearly number visually prominent and highlighted in bold RED.

6. VISUAL COMPARISON & PROGRESSION:
Show the difference visually across the sequence: before vs. after, wasted time vs. invested time, weak/starting state vs. developed/competent state.
Keep the same character throughout the carousel:
- Beginning slides: darker/cooler/less developed starting state.
- Ending slides: brighter/warmer/stronger/more confident posture and resolve.
The transformation should be obvious from the visual alone without needing to read a paragraph.

7. CHARACTER CONSISTENCY:
Use one original protagonist throughout the entire carousel.
Same face, hairstyle, athletic/muscular body proportions and overall identity on every slide.
Anime-inspired, muscular/athletic male character.
Dark clothing with subtle red accents.
Serious, disciplined, focused expression.
Do not randomly change the character between slides.

8. COMPOSITION & PLACEMENT:
Use 4:5 Instagram portrait format (1080×1350).
Character should occupy a major portion of the frame (cinematic medium/close framing).
Keep the character's face, eyes, and key action completely unobstructed.
Place text in a quiet high-contrast negative-space zone (minimum 100px side/top margins, 150px bottom margin).
Use cinematic environments and depth; avoid clutter.

9. OVERALL VISUAL STYLE:
Premium cinematic anime illustration (cinematic movie frame quality, not generic AI clip-art).
Dramatic lighting, detailed environment, strong shadows and highlights.
Dark → warm visual progression across the carousel.
High detail, sharp anatomy, realistic perspective.
No watermarks, random logos, unnecessary graphics, or UI elements.

10. THE GOLDEN RULE — SIMPLICITY:
ONE IDEA PER SLIDE. The viewer should understand the message in 1–2 seconds.
Prioritize in this order: HOOK → NUMBER → VISUAL → EMOTION.
NEVER: LONG TEXT → SMALL FONT → CLUTTERED IMAGE.
"""

BLUEPRINTS = {
    "dark": {"formats": ["small daily action vs huge yearly result", "daily habit compounding", "mistake and alternative"],
             "visual_arc": "dark/cool/isolated starting state → deliberate discipline → bright/warm confident strength",
             "palette": "deep charcoal, crisp white type with vibrant bold red number/keyword accents",
             "protagonist": "anime-inspired muscular athletic male, dark clothing with subtle red accents, disciplined serious expression",
             "audience": "a driven young adult building daily discipline and compounding habits"},
    "men": {"formats": ["daily workout compounding", "small daily action vs yearly result", "confidence through practice"],
            "visual_arc": "cool uncertainty/weak start → grounded practice → warm powerful competence and strength",
            "palette": "midnight navy/charcoal, crisp white type with bold red metric highlights",
            "protagonist": "anime-inspired muscular athletic male, dark athletic gear with subtle red accents, disciplined serious expression",
            "audience": "a young man building daily fitness, focus, and grounded competence"},
    "money": {"formats": ["small daily saving vs yearly wealth", "daily spend trade-off", "delayed gratification comparison"],
              "visual_arc": "cool-toned financial friction → deliberate daily choice → warm empowered stability and freedom",
              "palette": "deep charcoal, crisp white type with bold red calculation highlights",
              "protagonist": "anime-inspired muscular athletic male, dark sleek clothing with subtle red accents, focused serious expression",
              "audience": "someone who wants to see the huge yearly power of small daily financial choices"},
    "tech": {"formats": ["daily 30-min skill build vs 180h yearly mastery", "simple mechanism", "focus vs distraction"],
             "visual_arc": "cool cluttered distraction → focused practice → warm high-agency mastery",
             "palette": "midnight obsidian, pure white type with vivid red keyword accents",
             "protagonist": "anime-inspired muscular athletic male, dark techwear with subtle red accents, intense focused gaze",
             "audience": "a curious builder using daily focused habits to master technology and AI"},
    "finance": {"formats": ["daily dollar compounding", "risk trade-off", "small daily investment vs yearly capital"],
                "visual_arc": "uncertain cool start → disciplined daily capital allocation → warm commanding financial security",
                "palette": "charcoal/deep forest, pure white type with bold red numeric highlights",
                "protagonist": "anime-inspired muscular athletic male, sharp dark tailored clothing with subtle red accents, disciplined confident expression",
                "audience": "a disciplined person learning the compound interest of daily decisions"},
}


def plan_audit(plan, history):
    errors, warnings = [], []
    texts = [s.text for s in plan.slides]
    if len(tokens(texts[0])) > 16:
        errors.append("Cover exceeds 16 words; rewrite into one readable promise")
    for n, text in enumerate(texts, 1):
        if len(tokens(text)) > 40:
            errors.append(f"Slide {n} exceeds 40 words; reduce text before images")
        elif len(tokens(text)) > 10:
            warnings.append(f"Slide {n} text ({len(tokens(text))} words) exceeds preferred 3–8 words; shorten for mobile impact")
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


def slide_prompt(plan, slide, index, brand, niche, feedback=None, user_prompt=None):
    from .prompts import get_prompt
    total = len(plan.slides)
    last = index == total
    if index == 1:
        arc_note = "Beginning state: darker, cooler, moody atmosphere, starting/less developed state with focused determination."
    elif last:
        arc_note = "Final payoff: brightest, warmest lighting, peak physical and mental strength, victorious, confident, grounded resolve."
    else:
        pct = int((index / total) * 100)
        arc_note = f"Progressive transformation ({pct}% journey): transitioning from cool tones into warmer, brighter lighting, visibly stronger, disciplined and developing competence."

    swipe_note = (
        "This is the final payoff slide; no swipe marker."
        if last else
        "Leave the bottom-right 300x140px free for the swipe overlay added afterward."
    )
    user_prompt_section = (
        f"\n=== USER CREATIVE DIRECTION ===\n{user_prompt}\n"
        if user_prompt else ""
    )
    feedback_section = (
        f"\nCorrect the previous attempt's defects: {json.dumps(feedback)}"
        if feedback else ""
    )

    template = get_prompt("carousel_slide_prompt")
    if "{index}" in template and "{slide_text_json}" in template:
        try:
            return template.format(
                index=index,
                total=total,
                arc_note=arc_note,
                swipe_note=swipe_note,
                context_json=json.dumps([s.text for s in plan.slides], ensure_ascii=False),
                slide_text_json=json.dumps(slide.text, ensure_ascii=False),
                brand_json=json.dumps(brand, ensure_ascii=False),
                niche_json=json.dumps(BLUEPRINTS.get(niche, {}), ensure_ascii=False),
                scene_json=slide.model_dump_json(),
                user_prompt_section=user_prompt_section,
                feedback_section=feedback_section,
            )
        except (KeyError, IndexError, ValueError):
            pass

    return (
        template + "\n\n"
        f"Visual progression (Slide {index}/{total}): {arc_note}\n"
        f"{swipe_note}\n\n"
        f"Slide {index}/{total}. Full narrative context: "
        + json.dumps([s.text for s in plan.slides], ensure_ascii=False)
        + "\n\nRender ONLY the following exact text on THIS image, once, with correct spelling:\n"
        + json.dumps(slide.text, ensure_ascii=False)
        + "\n(Apply colour rule: render key numbers and crucial impact words in bold RED, and surrounding text in crisp WHITE. Do not print prompt instructions, metadata, or labels on the artwork.)\n"
        + "BRAND: " + json.dumps(brand, ensure_ascii=False) + "\n"
        + "SERIES DIRECTION: " + json.dumps(BLUEPRINTS.get(niche, {}), ensure_ascii=False) + "\n"
        + "SCENE: " + slide.model_dump_json()
        + (user_prompt_section if user_prompt else "")
        + feedback_section
    )


