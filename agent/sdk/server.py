"""Phase 9-3: FastAPI + SSE 스트리밍 서버.

POST /chat           — 메시지 전송, SSE로 assistant/tool/result 이벤트 스트림
GET  /sessions       — 세션 목록 (claude CLI 저장소 기준)
GET  /sessions/{id}  — 세션 메시지 전체
DELETE /sessions/{id}— 세션 삭제
"""

from __future__ import annotations

import json
import sys
from typing import AsyncIterator

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    delete_session,
    get_session_messages,
    list_sessions,
    query,
)

from agent.sdk.tools import ALL_TOOLS, ALLOWED_TOOL_NAMES


SYSTEM_PROMPT = """너는 대한민국 세법 전문 AI 세무사다. 사용자가 세무 상황·질문·계산을 주면:

1. 수치 계산이 필요하면 반드시 등록된 세무 tool을 호출해서 숫자를 뽑는다. 추정 금지.
2. 절세 전략을 제안할 때는 get_*_strategies tool을 호출해서 규칙 엔진의 결과를 활용한다.
3. 법령 인용이 필요하면 search_tax_law 또는 retrieve_legal_sources tool로 근거를 확보한다.
4. 회색지대 판단은 retrieve_legal_sources로 decisive_sources를 먼저 조회한다.
5. 모르는 것은 모른다고 답한다. 추측으로 법령·판례 인용 금지.

답변은 한국어로, 근거 조문·계산식을 명시한다.
"""


app = FastAPI(title="Tax Agent", version="0.9.3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_options(session_id: str | None) -> ClaudeAgentOptions:
    server = create_sdk_mcp_server(name="tax", version="0.1.0", tools=ALL_TOOLS)
    return ClaudeAgentOptions(
        mcp_servers={"tax": server},
        allowed_tools=ALLOWED_TOOL_NAMES,
        system_prompt=SYSTEM_PROMPT,
        resume=session_id,
    )


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


def _serialize_block(block) -> dict | None:
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}
    if isinstance(block, ThinkingBlock):
        return {"type": "thinking", "text": block.thinking}
    if isinstance(block, ToolUseBlock):
        return {"type": "tool_use", "name": block.name, "input": block.input, "id": block.id}
    if isinstance(block, ToolResultBlock):
        content = block.content
        if isinstance(content, list):
            text = "\n".join(
                c.get("text", "") if isinstance(c, dict) else str(c) for c in content
            )
        else:
            text = str(content)
        return {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "text": text,
            "is_error": bool(block.is_error),
        }
    return None


async def _stream(request: ChatRequest) -> AsyncIterator[dict]:
    options = _build_options(request.session_id)
    final_session_id: str | None = request.session_id
    try:
        async for message in query(prompt=request.message, options=options):
            if isinstance(message, SystemMessage):
                sid = message.data.get("session_id")
                if sid:
                    final_session_id = sid
                yield {"event": "system", "data": json.dumps({"subtype": message.subtype, "session_id": sid}, ensure_ascii=False)}
            elif isinstance(message, UserMessage):
                # tool_result는 여기로도 들어올 수 있음
                blocks = [b for b in (_serialize_block(bl) for bl in message.content) if b]
                for b in blocks:
                    yield {"event": "user", "data": json.dumps(b, ensure_ascii=False)}
            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    payload = _serialize_block(block)
                    if payload:
                        yield {"event": "assistant", "data": json.dumps(payload, ensure_ascii=False)}
            elif isinstance(message, ResultMessage):
                final_session_id = message.session_id or final_session_id
                yield {
                    "event": "result",
                    "data": json.dumps(
                        {
                            "session_id": message.session_id,
                            "duration_ms": message.duration_ms,
                            "num_turns": message.num_turns,
                            "total_cost_usd": message.total_cost_usd,
                            "is_error": message.is_error,
                        },
                        ensure_ascii=False,
                    ),
                }
    except Exception as e:
        yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}
    finally:
        yield {
            "event": "done",
            "data": json.dumps({"session_id": final_session_id}, ensure_ascii=False),
        }


@app.post("/chat")
async def chat(req: ChatRequest):
    return EventSourceResponse(_stream(req))


@app.get("/sessions")
async def sessions():
    try:
        return {"sessions": list_sessions()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/sessions/{session_id}")
async def session_messages(session_id: str):
    try:
        msgs = get_session_messages(session_id)
        return {"session_id": session_id, "messages": msgs}
    except Exception as e:
        raise HTTPException(404, str(e))


@app.delete("/sessions/{session_id}")
async def drop_session(session_id: str):
    try:
        delete_session(session_id)
        return {"deleted": session_id}
    except Exception as e:
        raise HTTPException(404, str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}
