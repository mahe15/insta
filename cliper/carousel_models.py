from __future__ import annotations

import ast
import math
import operator
import re

from pydantic import Field, model_validator

from .models import Model


class ContentScore(Model):
    hook: int = Field(ge=0, le=100)
    share: int = Field(ge=0, le=100)
    save: int = Field(ge=0, le=100)
    emotion: int = Field(ge=0, le=100)
    novelty: int = Field(ge=0, le=100)
    audience: int = Field(ge=0, le=100)
    brand: int = Field(ge=0, le=100)

    def total(self):
        return round(self.hook * .25 + self.share * .20 + self.save * .20 + self.emotion * .15
                     + self.novelty * .10 + self.audience * .05 + self.brand * .05, 2)


class Calculation(Model):
    expression: str = Field(max_length=150)
    result: float
    explanation: str = Field(max_length=300)

    @model_validator(mode="after")
    def verify(self):
        ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
               ast.Pow: operator.pow}
        expr = self.expression.strip()
        if "=" in expr:
            expr = expr.split("=")[0].strip()
        expr = expr.replace("×", "*").replace("÷", "/")
        expr = re.sub(r"(\d)\s*[xX]\s*(\d)", r"\1 * \2", expr)
        expr = re.sub(r"[$£€¥]", "", expr)
        expr = re.sub(r"/(?:month|week|day|year|yr|hr|hour|person|m|mo)\b", "", expr, flags=re.I)
        expr = re.sub(r"\bper\s+(?:month|week|day|year|yr|hr|hour|person|m|mo)\b", "", expr, flags=re.I)
        expr = re.sub(r"\b(?:days?|weeks?|months?|years?|yrs?|hrs?|hours?|mins?|minutes?|dollars?|cents?)\b", "", expr, flags=re.I)
        expr = re.sub(r"(\d),(\d)", r"\1\2", expr)
        expr = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", expr)
        expr = expr.replace("^", "**")
        m = re.match(r"^[\s\d\+\-\*\/\(\)\.\^]+", expr)
        if m and any(c.isdigit() for c in m.group(0)):
            expr = m.group(0).strip()

        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as exc:
            raise ValueError("Invalid arithmetic expression") from exc
        if len(list(ast.walk(tree))) > 40:
            raise ValueError("Calculation too complex")

        def compute(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float) and abs(node.value) < 1e12:
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in ops:
                left = compute(node.left)
                right = compute(node.right)
                if isinstance(node.op, ast.Pow) and (abs(right) > 100 or abs(left) > 1e6):
                    raise ValueError("Calculation too large")
                value = ops[type(node.op)](left, right)
                if type(value) not in (int, float) or abs(value) > 1e15 or not math.isfinite(value):
                    raise ValueError("Calculation intermediate must be a finite real number below 1e15")
                return value
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                return -compute(node.operand)
            raise ValueError("Only numeric arithmetic is allowed")
        try:
            value = compute(tree.body)
        except (ArithmeticError, OverflowError) as exc:
            raise ValueError("Invalid calculation") from exc
        if not math.isclose(value, self.result, rel_tol=.005, abs_tol=.05):
            raise ValueError("Mathematical claim does not match its arithmetic")
        return self



class Idea(Model):
    topic: str = Field(min_length=3, max_length=160)
    pillar: str = Field(min_length=2, max_length=60)
    hook: str = Field(min_length=3, max_length=140)
    angle: str = Field(min_length=10, max_length=2500)
    calculations: list[Calculation] = Field(default_factory=list, max_length=6)
    sources: list[str] = Field(default_factory=list, max_length=8)
    score: ContentScore


class Ideas(Model):
    ideas: list[Idea] = Field(min_length=1, max_length=10)


class Slide(Model):
    text: str = Field(min_length=1, max_length=250)
    environment: str = Field(min_length=2, max_length=150)
    action: str = Field(min_length=2, max_length=500)
    lighting: str = Field(min_length=2, max_length=250)
    camera: str = Field(min_length=2, max_length=250)
    mood: str = Field(min_length=2, max_length=150)
    image_prompt: str = Field(min_length=20, max_length=4000)


class CarouselPlan(Model):
    topic: str = Field(max_length=160)
    pillar: str = Field(max_length=60)
    hook: str = Field(max_length=140)
    caption: str = Field(min_length=1, max_length=1800)
    hashtags: list[str] = Field(max_length=5)
    slides: list[Slide] = Field(min_length=4, max_length=7)
    calculations: list[Calculation] = Field(default_factory=list, max_length=6)
    sources: list[str] = Field(default_factory=list, max_length=8)


class ContentReview(Model):
    approved: bool
    score: ContentScore
    issues: list[str] = Field(max_length=20)


class ImageReview(Model):
    text_matches: bool
    character_matches: bool
    composition_ok: bool
    issues: list[str] = Field(max_length=10)
    observed_text: str = Field(default="", max_length=1000)
