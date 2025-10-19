# agent.py
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession
from livekit.plugins import openai, deepgram, silero
import os
from assistant import Assistant

load_dotenv(".env")

async def entrypoint(ctx: agents.JobContext):
    llm = openai.LLM.with_ollama(
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    )

    # llm = llm,
    # tts = deepgram.TTS(),
    session = AgentSession(
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model=os.getenv("LLM_CHOICE", "gpt-4.1-mini")),
        tts = openai.TTS(voice="ballad"),
        vad=silero.VAD.load(),
    )

    await session.start(room=ctx.room, agent=Assistant())

    await session.generate_reply(
        instructions="Greet the user warmly and tell them you can help order food, book flights, or rides."
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
