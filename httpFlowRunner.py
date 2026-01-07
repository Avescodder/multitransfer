from __future__ import annotations

import json
import time
import uuid
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, List

import httpx


def now_ms() -> int:
    return int(time.time() * 1000)


def gen_uuid() -> str:
    return str(uuid.uuid4())


def try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def get_by_path(obj: Any, path: str) -> Any:
    if obj is None:
        return None

    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


VAR_RE = re.compile(r"\{\{\s*([^}]+)\s*\}\}")


def render(template: Any, ctx: Dict[str, Any]) -> Any:
    if template is None:
        return None

    if isinstance(template, str):
        def repl(m: re.Match) -> str:
            key = m.group(1)
            if key == "uuid":
                return gen_uuid()
            if key == "now_ms":
                return str(now_ms())
            if key.startswith("ctx."):
                return str(ctx.get(key[4:], ""))
            return str(ctx.get(key, ""))
        return VAR_RE.sub(repl, template)

    if isinstance(template, dict):
        return {k: render(v, ctx) for k, v in template.items()}

    if isinstance(template, list):
        return [render(v, ctx) for v in template]

    return template


@dataclass
class ExtractRule:
    var: str
    from_: str
    path: Optional[str] = None


@dataclass
class Step:
    name: str
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    json_body: Optional[Dict[str, Any]] = None
    expect_status: Optional[int] = None
    extracts: List[ExtractRule] = field(default_factory=list)
    retry: int = 0
    retry_delay_s: float = 0.2


class FlowRunner:
    def __init__(
        self,
        headers: Dict[str, str],
        proxy: str,
        timeout: float = 15.0,
    ) -> None:
        self.ctx: Dict[str, Any] = {
            "run_id": gen_uuid(),
            "started_at_ms": now_ms(),
        }

        self.client = httpx.Client(
            headers=headers,
            proxy=proxy,
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=5,
                max_keepalive_connections=5,
            ),
        )

    def close(self) -> None:
        self.client.close()

    def run(self, steps: List[Step]) -> Dict[str, Any]:
        for step in steps:
            self._run_step(step)
        self.ctx["finished_at_ms"] = now_ms()
        return self.ctx

    def _run_step(self, step: Step) -> None:
        attempt = 0
        while True:
            try:
                self._execute(step)
                return
            except Exception:
                attempt += 1
                if attempt > step.retry:
                    raise
                time.sleep(step.retry_delay_s)

    def _execute(self, step: Step) -> None:
        url = render(step.url, self.ctx)
        headers = render(step.headers, self.ctx)
        params = render(step.params, self.ctx)
        json_body = render(step.json_body, self.ctx)

        resp = self.client.request(
            method=step.method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
        )

        time.sleep(0.15)

        if step.expect_status and resp.status_code != step.expect_status:
            raise RuntimeError(f"{step.name}: {resp.status_code}")

        resp_json = try_json(resp.text)

        for rule in step.extracts:
            if rule.from_ == "json":
                val = get_by_path(resp_json, rule.path or "")
            elif rule.from_ == "status":
                val = resp.status_code
            elif rule.from_ == "headers":
                val = get_by_path(dict(resp.headers), rule.path or "")
            else:
                val = None
            self.ctx[rule.var] = val
