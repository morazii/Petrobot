import sys, json
sys.path.insert(0, '.')
from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()

base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
for suffix in ("/chat/completions", "/completions"):
    if base_url.endswith(suffix):
        base_url = base_url[: -len(suffix)]

headers = None
if "openrouter.ai" in base_url:
    headers = {"HTTP-Referer": "https://petrobot.app", "X-OpenRouter-Title": "PetroBot"}

client = OpenAI(
    base_url=base_url,
    api_key=os.getenv('LLM_API_KEY'),
    default_headers=headers
)

# ── Tool calling test ──────────────────────────────────────────────────────────
print("=" * 60)
print("PART 1: Tool Calling Test")
print("=" * 60)

dummy_tool = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"]
        }
    }
}]

resp = client.chat.completions.create(
    model=os.getenv('LLM_MODEL'),
    messages=[{"role": "user", "content": "What is the weather in Dubai?"}],
    tools=dummy_tool,
    tool_choice="auto"
)

msg = resp.choices[0].message
if msg.tool_calls:
    tc = msg.tool_calls[0]
    print(f"Tool called   : {tc.function.name}")
    print(f"Arguments     : {tc.function.arguments}")
    print("Tool calling  : SUPPORTED")
else:
    print("Direct answer :", msg.content)
    print("Tool calling  : NOT triggered (model answered directly)")

# ── Full agent test ────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("PART 2: Full Agent Test (3 real questions)")
print("=" * 60)

from backend.agent.agent import run_agent, new_conversation, add_user_message, add_assistant_message

questions = [
    "How many wells are there per field? Give me a ranked list.",
    "Which operator has the most drilling wells right now?",
    "Tell me about Delta-15.",
]

history = new_conversation()

for q in questions:
    print(f"\nUSER: {q}")
    history = add_user_message(history, q)
    r = run_agent(history)
    history = add_assistant_message(history, r)

    print(f"Tools called  : {r.tool_calls}")
    if r.error:
        print(f"Error         : {r.error}")
    print(f"Answer        : {r.text[:600]}")
    if r.table:
        print(f"Table rows    : {len(r.table)}  |  Sample: {r.table[0]}")
    if r.map_data:
        print(f"Map points    : {len(r.map_data)}")
    print("-" * 60)
