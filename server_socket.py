#!/usr/bin/env python3
"""
WebSocket bridge for the DataGen agent.
One persistent conversation per socket (no login).
"""

import asyncio
import json
import os
from typing import List

import websockets
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from datetime import datetime, timedelta
import random
import string

load_dotenv()

# -----------------  TOOLS  -----------------
@tool
def write_json(filepath: str, data: dict) -> str:
    """Write a Python dictionary as JSON to a file with pretty formatting."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return f"Successfully wrote JSON data to '{filepath}' ({len(json.dumps(data))} characters)."
    except Exception as e:
        return f"Error writing JSON: {str(e)}"


@tool
def read_json(filepath: str) -> str:
    """Read and return the contents of a JSON file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(data, indent=2)
    except FileNotFoundError:
        return f"Error: File '{filepath}' not found."
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON in file - {str(e)}"
    except Exception as e:
        return f"Error reading JSON: {str(e)}"


@tool
def generate_sample_users(
    first_names: List[str],
    last_names: List[str],
    domains: List[str],
    min_age: int,
    max_age: int,
) -> dict:
    """Generate sample user data. Count == len(first_names)."""
    if not first_names:
        return {"error": "first_names list cannot be empty"}
    if not last_names:
        return {"error": "last_names list cannot be empty"}
    if not domains:
        return {"error": "domains list cannot be empty"}
    if min_age > max_age:
        return {"error": f"min_age ({min_age}) cannot be greater than max_age ({max_age})"}
    if min_age < 0 or max_age < 0:
        return {"error": "ages must be non-negative"}

    users = []
    count = len(first_names)
    for i in range(count):
        first = first_names[i]
        last = last_names[i % len(last_names)]
        domain = domains[i % len(domains)]
        email = f"{first.lower()}.{last.lower()}@{domain}"
        user = {
            "id": i + 1,
            "firstName": first,
            "lastName": last,
            "email": email,
            "username": f"{first.lower()}{random.randint(100, 999)}",
            "age": random.randint(min_age, max_age),
            "registeredAt": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
        }
        users.append(user)
    return {"users": users, "count": len(users)}


TOOLS = [write_json, read_json, generate_sample_users]

# -----------------  AGENT  -----------------
llm = ChatOpenAI(
    model=os.getenv("MODEL", "gpt-4"),
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE_URL"),
)

SYSTEM_MESSAGE = (
    "You are DataGen, a helpful assistant that generates sample data for applications. "
    "To generate users, you need: first_names (list), last_names (list), domains (list), min_age, max_age. "
    "Fill in these values yourself without asking for them. "
    "When asked to save users, first generate them with the tool, then immediately use write_json with the result. "
    "If the user refers to 'those users' from a previous request, ask them to specify the details again."
)

agent = create_react_agent(llm, TOOLS, prompt=SYSTEM_MESSAGE)

# -----------------  WS LOGIC  -----------------
CONNECTIONS = {}  # websocket -> List[BaseMessage] (history)


async def handler(websocket: websockets.WebSocketServerProtocol):
    """One task per client. Keeps history in memory."""
    history: List[BaseMessage] = []
    CONNECTIONS[websocket] = history
    try:
        await websocket.send(json.dumps({"type": "system", "text": "Connected to DataGen agent 🚀"}))
        async for msg in websocket:
            try:
                data = json.loads(msg)
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue

                # Run agent
                result = agent.invoke(
                    {"messages": history + [HumanMessage(content=user_text + "\n /no_think")]},
                    config={"recursion_limit": 50},
                )
                ai_msg: AIMessage = result["messages"][-1]

                # Update history
                history.extend([HumanMessage(content=user_text), ai_msg])

                # Send back
                await websocket.send(json.dumps({"type": "agent", "text": ai_msg.content}))

            except Exception as ex:
                await websocket.send(json.dumps({"type": "error", "text": f"Server error: {ex}"}))
    finally:
        CONNECTIONS.pop(websocket, None)


async def main():
    host = os.getenv("WS_HOST", "0.0.0.0")
    port = int(os.getenv("WS_PORT", 8765))
    print(f"🟢 WebSocket server ready  ws://{host}:{port}")
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())