

from __future__ import annotations

import os
from typing import List, Dict, AsyncGenerator

import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from agents import (
    Agent,
    Runner,
    RunConfig,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
)
from openai.types.responses import ResponseTextDeltaEvent

# ---------------------------------------------------------------------------
# Environment & model setup
# ---------------------------------------------------------------------------

load_dotenv()

gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise EnvironmentError("GEMINI_API_KEY is missing. Add it to your .env file.")

external_client = AsyncOpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=external_client,
)

config = RunConfig(
    model=model,
    model_provider=external_client,
    tracing_disabled=True,
)

agent = Agent(
    name="sidra's Agent",
    instructions=(
        "You are a helpful and knowledgeable language learning assistant. "
        "Your goal is to help users improve their language skills through clear explanations, "
        "practice exercises, vocabulary guidance, grammar rules, and answering language-related questions. "
        "Always stay focused on language learning topics and provide responses in a supportive and easy-to-understand way. "
        "You can assist with all types of languages and provide information about what a word means in english, "
        "including translations and context-based meanings across various languages."
    ),
    model=model,
)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Sidra Agent API", version="1.0.0")

# If your frontend and backend are on different origins, enable CORS:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: narrow in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str = Field(..., examples=["user", "assistant"])
    content: str

class ChatRequest(BaseModel):
    history: List[Message] = Field(  # previous messages; can be empty
        default_factory=list,
        description="Existing conversation history as an array of role/content objects.",
    )
    user_input: str = Field(..., description="The user's latest prompt.")

class ChatResponse(BaseModel):
    assistant_reply: str


# ---------------------------------------------------------------------------
# Helper – run the agent asynchronously and capture full text
# ---------------------------------------------------------------------------

async def _run_agent(history: List[Dict[str, str]]) -> str:
    """Runs the agent with streaming but buffers the full reply."""
    result = Runner.run_streamed(agent, input=history, run_config=config)
    assistant_reply = ""

    async for event in result.stream_events():
        if (
            event.type == "raw_response_event"
            and isinstance(event.data, ResponseTextDeltaEvent)
        ):
            assistant_reply += event.data.delta

    return assistant_reply


# ---------------------------------------------------------------------------
# Non‑streaming endpoint
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse, summary="Chat – JSON response")
async def chat_endpoint(req: ChatRequest):
    """Returns the assistant's full reply as JSON."""
    # Build history for the agent
    history: List[Dict[str, str]] = [m.dict() for m in req.history]
    history.append({"role": "user", "content": req.user_input})

    try:
        assistant_reply = await _run_agent(history)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"assistant_reply": assistant_reply}


# ---------------------------------------------------------------------------
# Streaming endpoint (Server‑Sent Events / chunked text)
# ---------------------------------------------------------------------------

@app.post("/chat/stream", response_class=StreamingResponse, summary="Chat – stream reply")
async def chat_stream_endpoint(req: ChatRequest):
    """Streams the assistant's reply token‑by‑token (plain text chunks)."""
    history: List[Dict[str, str]] = [m.dict() for m in req.history]
    history.append({"role": "user", "content": req.user_input})

    async def _token_generator() -> AsyncGenerator[str, None]:
        result = Runner.run_streamed(agent, input=history, run_config=config)
        async for event in result.stream_events():
            if (
                event.type == "raw_response_event"
                and isinstance(event.data, ResponseTextDeltaEvent)
            ):
                # Each token is sent as‑is; the frontend can concat.
                yield event.data.delta

    # `text/plain` so the browser treats it as a simple stream.
    return StreamingResponse(_token_generator(), media_type="text/plain")


# ---------------------------------------------------------------------------
# Health check (optional)
# ---------------------------------------------------------------------------

@app.get("/health", summary="Health check")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Optional: CLI (keep the original terminal chat behaviour)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Re‑use the same module as a script for quick testing.
    import asyncio

    async def _cli():
        history = []
        print("\nWelcome to Sidra's Agent (FastAPI CLI mode). Type 'exit' to quit.\n")
        try:
            while True:
                user_input = input("You: ")
                if user_input.lower() in {"exit", "quit"}:
                    break
                history.append({"role": "user", "content": user_input})
                reply = await _run_agent(history)
                print(f"Assistant: {reply}\n")
                history.append({"role": "assistant", "content": reply})
        except (KeyboardInterrupt, EOFError):
            print("\nExiting…")

    asyncio.run(_cli())
