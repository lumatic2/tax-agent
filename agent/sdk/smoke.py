"""Phase 9-1 스모크: Agent SDK + claude CLI + tax_calculator 왕복 1회 확인."""

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
    tool,
)

from tax_calculator import calculate_tax


@tool(
    "calculate_income_tax",
    "대한민국 개인 종합소득세 산출세액을 과세표준(원) 기준으로 계산한다. 2024년 귀속 세율표 기준.",
    {"taxable_income": int},
)
async def calculate_income_tax_tool(args):
    result = calculate_tax(args["taxable_income"])
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"과세표준 {args['taxable_income']:,}원 → "
                    f"산출세액 {result['산출세액']:,}원 "
                    f"(적용세율 {result['적용세율'] * 100:.0f}%, "
                    f"누진공제 {result['누진공제액']:,}원)"
                ),
            }
        ]
    }


async def main() -> None:
    server = create_sdk_mcp_server(
        name="tax-agent-smoke",
        version="0.1.0",
        tools=[calculate_income_tax_tool],
    )

    options = ClaudeAgentOptions(
        mcp_servers={"tax": server},
        allowed_tools=["mcp__tax__calculate_income_tax"],
        system_prompt=(
            "너는 대한민국 세법 전문 에이전트다. 세금 계산이 필요한 질문에는 "
            "반드시 calculate_income_tax 툴을 호출해서 수치를 뽑고, 근거와 함께 답한다."
        ),
    )

    prompt = "과세표준 5천만원일 때 종합소득세 산출세액은 얼마야? 툴 써서 계산하고 근거도 알려줘."

    print(f"[USER] {prompt}\n")

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[CLAUDE] {block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[TOOL USE] {block.name} {block.input}")
        elif isinstance(message, ResultMessage):
            cost = message.total_cost_usd or 0
            print(f"\n[RESULT] duration={message.duration_ms}ms cost=${cost:.6f}")


if __name__ == "__main__":
    anyio.run(main)
