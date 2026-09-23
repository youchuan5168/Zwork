"""Call configured provider using synthetic greeting only; no DB/user data."""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import Settings  # noqa: E402
from app.agents.providers import DeepSeekChatProvider, OpenAIResponsesProvider  # noqa: E402
from app.agents.contracts import ProviderError  # noqa: E402


async def main():
    config = Settings()
    config.validate_runtime()
    provider_type = DeepSeekChatProvider if config.agent_provider == "deepseek_chat" else OpenAIResponsesProvider
    provider = provider_type(config.openai_api_key, api_url=config.agent_api_url)
    try:
        result = await provider.complete(model=config.agent_model, instructions="Reply briefly to the greeting.",
                                         items=[{"role": "user", "content": "Hello. This is a synthetic connection test."}],
                                         tools=[], max_output_tokens=100, timeout=20)
        print(json.dumps({"ok": bool(result.text), "provider": config.agent_provider,
                          "input_tokens": result.input_tokens, "output_tokens": result.output_tokens}))
    except ProviderError as error:
        print(json.dumps({"ok": False, "error_code": str(error)}))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
