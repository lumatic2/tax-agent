"""Phase 9-2 스모크: 전체 7개 tool을 Agent SDK에 붙이고 다세목 질문 왕복 확인."""

import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import anyio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
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


PROMPTS = [
    # 소득세 계산 + 전략
    "총급여 7천만원 근로자인데, 월세 월 50만원 내고 부양가족 2명(배우자·자녀) 있어. "
    "올해 예상 세금이랑 쓸 만한 절세 전략 3개 추천해줘.",
]


async def main() -> None:
    server = create_sdk_mcp_server(name="tax", version="0.1.0", tools=ALL_TOOLS)
    options = ClaudeAgentOptions(
        mcp_servers={"tax": server},
        allowed_tools=ALLOWED_TOOL_NAMES,
        system_prompt=SYSTEM_PROMPT,
    )

    for prompt in PROMPTS:
        print(f"\n{'='*60}\n[USER] {prompt}\n{'='*60}\n")
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"[CLAUDE]\n{block.text}\n")
                    elif isinstance(block, ToolUseBlock):
                        if block.name.startswith("mcp__tax__"):
                            print(f"[TOOL] {block.name} {block.input}")
            elif isinstance(message, ResultMessage):
                cost = message.total_cost_usd or 0
                print(f"[RESULT] duration={message.duration_ms}ms cost=${cost:.4f}")


if __name__ == "__main__":
    anyio.run(main)
