"""Provider-specific API calls behind one validated editorial interface.

Grok and Gemini use their official OpenAI-compatible endpoints. The OpenAI SDK
is a transport client here; those requests go directly to xAI or Google.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from .config import AISettings
from .models import Proposals


@asynccontextmanager
async def editorial_client(cfg, settings):
    if settings.provider == "chatgpt_browser":
        from .browser_provider import BrowserEditorialClient
        async with BrowserEditorialClient(cfg) as client:
            yield client
    else:
        from openai import AsyncOpenAI
        async with AsyncOpenAI(api_key=settings.key, base_url=settings.base_url,
                               timeout=120, max_retries=2) as transport:
            yield EditorialClient(transport, settings)


async def verify_model(client, settings: AISettings):
    if settings.provider == "gemini":
        # Google's compatibility documentation exposes models.list for discovery.
        page = await client.models.list()
        async for model in page:
            if model.id.removeprefix("models/") == settings.model.removeprefix("models/"):
                return
        raise ValueError(f"Gemini model {settings.model} was not returned by the model list")
    await client.models.retrieve(settings.model)


def clean_for_gemini(schema: dict) -> dict:
    defs = schema.get("$defs") or schema.get("definitions") or {}
    allowed = {"type", "properties", "items", "required", "description", "nullable", "enum"}

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"].split("/")[-1]
                return resolve(defs[ref])
            clean = {}
            for k, v in node.items():
                if k == "properties" and isinstance(v, dict):
                    clean["properties"] = {pk: resolve(pv) for pk, pv in v.items()}
                elif k in allowed:
                    clean[k] = resolve(v)
            return clean
        elif isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(schema)


class EditorialClient:
    def __init__(self, client, settings: AISettings):
        self.client, self.settings = client, settings

    async def text(self, instructions: str, prompt: str, max_tokens: int) -> str:
        if self.settings.provider == "openai":
            response = await self.client.responses.create(
                model=self.settings.model, store=False, max_output_tokens=max_tokens,
                instructions=instructions, input=prompt)
            if response.status != "completed" or not response.output_text:
                raise ValueError("OpenAI context analysis was refused or incomplete. Retry or change OPENAI_MODEL.")
            return response.output_text
        response = await self.client.chat.completions.create(**self.chat_args(instructions, prompt, max_tokens))
        message = self.complete_message(response)
        if not message.content or not message.content.strip():
            raise ValueError(f"{self.settings.provider} returned an empty context response")
        return message.content

    async def proposals(self, instructions: str, prompt: str, max_tokens: int) -> Proposals:
        if self.settings.provider == "openai":
            response = await self.client.responses.parse(
                model=self.settings.model, store=False, max_output_tokens=max_tokens,
                instructions=instructions, input=prompt, text_format=Proposals)
            if response.status != "completed" or response.output_parsed is None:
                raise ValueError("OpenAI editorial response was refused or incomplete. Try again.")
            return Proposals.model_validate(response.output_parsed)
        # Use create + local validation so refusal/truncation is checked before JSON parsing.
        if self.settings.provider == "gemini":
            response_format = {"type": "json_schema", "json_schema": {
                "name": "clip_proposals", "schema": clean_for_gemini(Proposals.model_json_schema())}}
        else:
            response_format = {"type": "json_schema", "json_schema": {
                "name": "clip_proposals", "strict": True, "schema": Proposals.model_json_schema()}}
        response = await self.client.chat.completions.create(
            **self.chat_args(instructions, prompt, max_tokens),
            response_format=response_format)
        message = self.complete_message(response)
        if not message.content:
            raise ValueError(f"{self.settings.provider} returned no clip proposals")
        return Proposals.model_validate_json(message.content)

    def chat_args(self, instructions, prompt, max_tokens):
        # Reserve room for reasoning tokens in these providers' combined completion budget.
        return {"model": self.settings.model, "max_tokens": max_tokens + 4096,
                "reasoning_effort": "low",
                "messages": [{"role": "system", "content": instructions},
                             {"role": "user", "content": prompt}]}

    def complete_message(self, response):
        if not response.choices or response.choices[0].finish_reason != "stop":
            raise ValueError(f"{self.settings.provider} response was blocked or incomplete. Retry or change its model.")
        message = response.choices[0].message
        if message.refusal:
            raise ValueError(f"{self.settings.provider} declined this editorial request")
        return message
