from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Financial Study Chatbot")


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    response: str


@app.post("/api/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    from graph.builder import build_chat_graph

    graph = build_chat_graph()
    result = graph.invoke({"user_input": req.query})
    return ChatResponse(response=result.get("chatbot_response", ""))


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main() -> None:
    uvicorn.run("frontend.server:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
