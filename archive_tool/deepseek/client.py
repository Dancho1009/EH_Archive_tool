from __future__ import annotations

import json
from urllib import request as urlrequest


def deepseek_chat(
    api_key: str,
    model: str,
    base_url: str,
    system_prompt: str,
    user_prompt: str,
    timeout_sec: int,
) -> dict:
    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": 0.1,
    }
    req = urlrequest.Request(
        url=f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=timeout_sec) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return json.loads(data["choices"][0]["message"]["content"])


def parse_confidence(value) -> int:
    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))
    if value is None:
        return 0
    text = str(value).strip().lower()
    label_map = {
        "high": 90,
        "medium": 70,
        "low": 40,
        "very high": 95,
        "very low": 20,
    }
    if text in label_map:
        return label_map[text]
    import re

    matched = re.search(r"\d+", text)
    if matched:
        return max(0, min(100, int(matched.group(0))))
    return 0
