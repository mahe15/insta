"""Reusable carousel art direction and deterministic pre-generation checks."""
from __future__ import annotations

import json
import re

from .editorial import similarity, tokens

CAROUSEL_BRIEF = """
Build an original, high-impact Instagram carousel following these 10 core design rules:

1. SPLIT-SCENE LAYOUT (THE KEY FORMAT):
Each carousel slide is ONE image divided into TWO VERTICALLY-STACKED SCENES.
The top half shows Scene A, the bottom half shows Scene B.
Both halves feature the SAME CHARACTER in DIFFERENT ENVIRONMENTS doing DIFFERENT ACTIONS.
This creates an instant visual contrast (before/after, cause/effect, problem/solution, sacrifice/reward).
The horizontal dividing line between the two halves should be a natural, clean visual break.
Each half is approximately 1080×675 pixels within the full 1080×1350 portrait canvas.

2. FONT & TYPOGRAPHY:
Use a bold, modern sans-serif font with a thick/heavy weight similar to Montserrat ExtraBold, Anton, or Bebas Neue.
Font must be clean, simple and highly readable on a phone.
STRICTLY NEVER use decorative, cursive, thin, script, or handwritten fonts.

3. FONT SIZE:
Text must be large, punchy and dominant within each half.
Main headline / primary numbers: approximately 8–12% of each half's height.
Never make text small just to fit more words. Shorten the sentence instead.

4. TEXT COLOUR:
Strict primary text palette:
- Main text: solid crisp WHITE.
- Important numbers / key impact keywords: vibrant bold RED or ORANGE.
Use only these primary text colours. Example: "Quit" in WHITE, "Porn" in RED on the top half; "Energy" in RED, "Back" in WHITE on the bottom half.
Maintain strong contrast against the background at all times.

5. TEXT ON EACH HALF:
Each half has its OWN short bold text line (2–5 words max per half).
The top-half text and bottom-half text form a contrasting pair that tells the slide's story.
Examples: "Quit Porn" / "Energy Back", "Build Body" / "Confidence Back", "I only got 10 views" / "10 Views:".
The TEXT IS PART OF THE IMAGE, rendered directly over each scene.

6. VISUAL CONTRAST WITHIN EACH SLIDE:
The two halves must show a clear visual contrast:
- TOP HALF: The problem, sacrifice, starting state, daily action, or loss. Darker, cooler, moodier atmosphere.
- BOTTOM HALF: The reward, result, transformation, payoff, or gain. Warmer, brighter, more energetic atmosphere.
The character's pose, expression, and surroundings change between halves to tell the story visually.

7. CHARACTER CONSISTENCY:
Use one original protagonist throughout the entire carousel AND across BOTH halves of each slide.
Same face, hairstyle, body proportions and identity everywhere.
The character should be recognizable as the same person in different situations.
Do NOT randomly change the character between slides or halves.

8. COMPOSITION & PLACEMENT:
Use 4:5 Instagram portrait format (1080×1350) total canvas.
Each half (~1080×675) is a complete cinematic scene with the character prominently placed.
Place text in a high-contrast zone within each half (centre-bottom of each half works best).
Use cinematic environments with depth and detail; avoid clutter.
Keep the character's face and key action unobstructed by text.

9. OVERALL VISUAL STYLE:
Premium cinematic anime illustration (cinematic movie frame quality, not generic AI clip-art).
Dramatic lighting, detailed environments, strong shadows and highlights.
High detail, sharp anatomy, realistic perspective.
No watermarks, random logos, unnecessary graphics, decorative borders, or UI elements.

10. THE GOLDEN RULE — INSTANT CONTRAST:
Each slide tells ONE contrasting story through TWO scenes. The viewer grasps the message in 1–2 seconds.
Prioritize: VISUAL CONTRAST → BOLD TEXT → EMOTION → CHARACTER.
NEVER: LONG TEXT → SMALL FONT → SINGLE BORING SCENE → CLUTTERED IMAGE.
"""

BLUEPRINTS = {
    "dark": {"formats": ["sacrifice / reward split", "bad habit quit / benefit gained", "daily action / yearly compounding", "mistake / correct alternative"],
             "split_style": "Top half: dark, moody, isolated problem state. Bottom half: bright, warm, disciplined reward state.",
             "visual_arc": "Each slide contrasts a dark sacrifice/problem (top) with its bright reward/outcome (bottom)",
             "palette": "deep charcoal backgrounds, crisp white type with vibrant bold red/orange keyword accents",
             "protagonist": "anime-inspired muscular athletic male, dark clothing with subtle red accents, disciplined serious expression",
             "audience": "a driven young adult building daily discipline and compounding habits"},
    "men": {"formats": ["weak habit / strong alternative", "daily workout / yearly body transformation", "avoidance / confidence through action"],
            "split_style": "Top half: hesitant, untrained, uncertain. Bottom half: trained, confident, powerful.",
            "visual_arc": "Each slide contrasts a weak starting state (top) with grounded competence (bottom)",
            "palette": "midnight navy/charcoal, crisp white type with bold red metric highlights",
            "protagonist": "anime-inspired muscular athletic male, dark athletic gear with subtle red accents, disciplined serious expression",
            "audience": "a young man building daily fitness, focus, and grounded competence"},
    "money": {"formats": ["wasteful spending / smart saving", "daily latte cost / yearly wealth", "instant gratification / delayed reward"],
              "split_style": "Top half: impulsive spending, consumerism. Bottom half: financial freedom, strategic calm.",
              "visual_arc": "Each slide contrasts financial friction (top) with empowered stability (bottom)",
              "palette": "deep charcoal, crisp white type with bold red calculation highlights",
              "protagonist": "anime-inspired muscular athletic male, dark sleek clothing with subtle red accents, focused serious expression",
              "audience": "someone who wants to see the huge yearly power of small daily financial choices"},
    "tech": {"formats": ["distraction / focused learning", "30-min daily skill / yearly mastery", "scroll doom / build future"],
             "split_style": "Top half: distracted, cluttered screens, wasted time. Bottom half: focused, coding/building, mastery.",
             "visual_arc": "Each slide contrasts digital distraction (top) with high-agency mastery (bottom)",
             "palette": "midnight obsidian, pure white type with vivid red keyword accents",
             "protagonist": "anime-inspired muscular athletic male, dark techwear with subtle red accents, intense focused gaze",
             "audience": "a curious builder using daily focused habits to master technology and AI"},
    "finance": {"formats": ["daily spend / yearly loss", "risky shortcut / steady compound growth", "ignorance / financial literacy"],
                "split_style": "Top half: uncertain, risky, uninformed. Bottom half: commanding, secure, strategic.",
                "visual_arc": "Each slide contrasts uncertain financial friction (top) with commanding security (bottom)",
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
    blueprint = BLUEPRINTS.get(niche, {})

    # Build split-scene descriptions if present
    has_split = slide.top_scene is not None and slide.bottom_scene is not None
    if has_split:
        top = slide.top_scene
        bottom = slide.bottom_scene
        split_description = (
            f"TOP HALF (~1080×675): Scene showing '{top.text}'. "
            f"Environment: {top.environment}. Action: {top.action}. "
            f"Lighting: {top.lighting}. Mood: {top.mood}. "
            f"Render the text '{top.text}' in bold over this scene.\n"
            f"BOTTOM HALF (~1080×675): Scene showing '{bottom.text}'. "
            f"Environment: {bottom.environment}. Action: {bottom.action}. "
            f"Lighting: {bottom.lighting}. Mood: {bottom.mood}. "
            f"Render the text '{bottom.text}' in bold over this scene."
        )
    else:
        split_description = f"Single scene: {slide.environment}. {slide.action}"

    if index == 1:
        arc_note = "Opening contrast: strongest difference between top (dark problem) and bottom (bright reward) to hook attention."
    elif last:
        arc_note = "Final payoff: the most dramatic and satisfying contrast. Top shows the biggest sacrifice, bottom shows the ultimate reward."
    else:
        pct = int((index / total) * 100)
        arc_note = f"Mid-journey contrast ({pct}%): deepening the narrative. Top half shows a progressively harder challenge, bottom half shows a progressively greater reward."

    swipe_note = (
        "This is the final payoff slide; no swipe marker."
        if last else
        "Leave the bottom-right 300×140px of the bottom half free for the swipe overlay added afterward."
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
                niche_json=json.dumps(blueprint, ensure_ascii=False),
                scene_json=slide.model_dump_json(),
                split_scene_json=json.dumps({"has_split": has_split, "description": split_description}, ensure_ascii=False),
                user_prompt_section=user_prompt_section,
                feedback_section=feedback_section,
            )
        except (KeyError, IndexError, ValueError):
            pass

    return (
        template + "\n\n"
        f"=== SPLIT-SCENE LAYOUT ===\n"
        f"{split_description}\n\n"
        f"Visual progression (Slide {index}/{total}): {arc_note}\n"
        f"{swipe_note}\n\n"
        f"Slide {index}/{total}. Full narrative context: "
        + json.dumps([s.text for s in plan.slides], ensure_ascii=False)
        + "\n\nRender ONLY the following exact text on THIS image, with correct spelling:\n"
        + json.dumps(slide.text, ensure_ascii=False)
        + (f"\nTOP HALF TEXT: {json.dumps(slide.top_scene.text, ensure_ascii=False)}" if has_split else "")
        + (f"\nBOTTOM HALF TEXT: {json.dumps(slide.bottom_scene.text, ensure_ascii=False)}" if has_split else "")
        + "\n(Apply colour rule: render key numbers and crucial impact words in bold RED or ORANGE, and surrounding text in crisp WHITE. Do not print prompt instructions, metadata, or labels on the artwork.)\n"
        + "BRAND: " + json.dumps(brand, ensure_ascii=False) + "\n"
        + "SERIES DIRECTION: " + json.dumps(blueprint, ensure_ascii=False) + "\n"
        + "SCENE: " + slide.model_dump_json()
        + (user_prompt_section if user_prompt else "")
        + feedback_section
    )


