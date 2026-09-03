try:
    import tiktoken

    _HAS_TIKTOKEN = True
except ImportError:
    _HAS_TIKTOKEN = False


class TokenBudgetExceeded(Exception):
    pass


_MODEL_CONTEXT_WINDOWS = {
    "llama-3.3-70b-versatile": 32768,
    "llama-3.1-8b-instant": 8192,
    "groq/compound": 131072,
    "groq/compound-mini": 131072,
    "openai/gpt-oss-20b": 131072,
    "openai/gpt-oss-120b": 131072,
    "gemini-3.6-flash": 1_048_576,
}

_DEFAULT_CONTEXT_WINDOW = 16384

_TIKTOKEN_ALIAS = {
    "llama-3.3-70b-versatile": "cl100k_base",
    "llama-3.1-8b-instant": "cl100k_base",
    "groq/compound": "cl100k_base",
    "groq/compound-mini": "cl100k_base",
    "openai/gpt-oss-20b": "cl100k_base",
    "openai/gpt-oss-120b": "cl100k_base",
    "gemini-3.6-flash": "cl100k_base",
}


def get_model_context_window(model: str) -> int:
    return _MODEL_CONTEXT_WINDOWS.get(model, _DEFAULT_CONTEXT_WINDOW)


def _get_encoding(model: str):
    if not _HAS_TIKTOKEN:
        return None
    enc_name = _TIKTOKEN_ALIAS.get(model)
    try:
        if enc_name:
            return tiktoken.get_encoding(enc_name)
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    if _HAS_TIKTOKEN:
        enc = _get_encoding("gpt-3.5-turbo")
        if enc:
            return len(enc.encode(text))
    return max(1, len(text) // 4)


def estimate_tokens_for_model(text: str, model: str) -> int:
    if not text:
        return 0
    if _HAS_TIKTOKEN:
        enc = _get_encoding(model)
        if enc:
            return len(enc.encode(text))
    return max(1, len(text) // 4)


def count_tokens_in_messages(messages: list, model: str = "gpt-3.5-turbo") -> int:
    total = 0
    for msg in messages:
        if isinstance(msg, str):
            total += estimate_tokens_for_model(msg, model)
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total += estimate_tokens_for_model(part.get("text", ""), model)
        else:
            total += estimate_tokens_for_model(content, model)
        total += estimate_tokens_for_model(msg.get("role", ""), model)
    total += 2
    return total


def truncate_to_token_budget(
    text: str, max_tokens: int, model: str = "gpt-3.5-turbo"
) -> str:
    if not text:
        return text
    token_count = estimate_tokens_for_model(text, model)
    if token_count <= max_tokens:
        return text
    if _HAS_TIKTOKEN:
        enc = _get_encoding(model)
        if enc:
            tokens = enc.encode(text)
            return enc.decode(tokens[:max_tokens])
    ratio = max_tokens / token_count
    char_budget = max(1, int(len(text) * ratio))
    return text[:char_budget]


def truncate_messages_to_budget(
    messages: list, max_tokens: int, model: str = "gpt-3.5-turbo"
) -> list:
    if not messages:
        return messages
    total = count_tokens_in_messages(messages, model)
    if total <= max_tokens:
        return messages
    result = list(messages)
    while result and count_tokens_in_messages(result, model) > max_tokens:
        last = result.pop()
        if not result:
            break
        if isinstance(last, str):
            continue
        content = last.get("content", "")
        if isinstance(content, str) and content:
            budget = max_tokens - count_tokens_in_messages(result, model)
            budget = max(
                0, budget - estimate_tokens_for_model(last.get("role", ""), model) - 2
            )
            truncated = truncate_to_token_budget(content, budget, model)
            last["content"] = truncated
            result.append(last)
            break
    return result


def enforce_budget(
    messages: list, max_context_tokens: int, safety_margin: float = 0.9
) -> list:
    budget = int(max_context_tokens * safety_margin)
    total = count_tokens_in_messages(messages)
    if total <= budget:
        return messages
    return truncate_messages_to_budget(messages, budget)
