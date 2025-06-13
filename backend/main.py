from __future__ import annotations

import os
from typing import List, Dict, AsyncGenerator

import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents import Agent, Runner, RunConfig, AsyncOpenAI, OpenAIChatCompletionsModel
from openai.types.responses import ResponseTextDeltaEvent

# Load environment variables
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
    name="Sidra's Agent",
    instructions=(
        "You are a helpful and knowledgeable language learning assistant. "
        "Your goal is to help users improve their language skills through clear explanations, "
        "practice exercises, vocabulary guidance, grammar rules, and answering language-related questions. "
        "You can assist with all types of languages and provide information about what a word means in English, "
        "including translations and context-based meanings."
    ),
    model=model,
)

# Create FastAPI app
app = FastAPI(title="Sidra Agent API", version="1.0.0")

# ✅ Allow Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://language-asistant-agent.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request and response schemas
class Message(BaseModel):
    role: str = Field(..., examples=["user", "assistant"])
    content: str

class ChatRequest(BaseModel):
    history: List[Message] = Field(default_factory=list)
    user_input: str

class ChatResponse(BaseModel):
    assistant_reply: str

# Agent runner
async def _run_agent(history: List[Dict[str, str]]) -> str:
    result = Runner.run_streamed(agent, input=history, run_config=config)
    assistant_reply = ""

    async for event in result.stream_events():
        if (
            event.type == "raw_response_event"
            and isinstance(event.data, ResponseTextDeltaEvent)
        ):
            assistant_reply += event.data.delta

    return assistant_reply

# Routes
@app.get("/")
async def root():
    return {"message": "✅ Sidra Agent is running!"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    history = [m.dict() for m in req.history]
    history.append({"role": "user", "content": req.user_input})

    try:
        assistant_reply = await _run_agent(history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"assistant_reply": assistant_reply}

@app.post("/chat/stream", response_class=StreamingResponse)
async def chat_stream_endpoint(req: ChatRequest):
    history = [m.dict() for m in req.history]
    history.append({"role": "user", "content": req.user_input})

    async def _token_generator() -> AsyncGenerator[str, None]:
        result = Runner.run_streamed(agent, input=history, run_config=config)
        async for event in result.stream_events():
            if (
                event.type == "raw_response_event"
                and isinstance(event.data, ResponseTextDeltaEvent)
            ):
                yield event.data.delta

    return StreamingResponse(_token_generator(), media_type="text/plain")
