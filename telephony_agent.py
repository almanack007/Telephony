import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from aiohttp import web
from twilio.twiml.voice_response import VoiceResponse, Connect

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import deepgram, openai, cartesia, silero

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("telephony-agent")

# This function answers the phone call from Twilio.
async def handle_request(req: web.Request):
    logger.info("Answering the phone call from Twilio...")
    host = req.headers.get("X-Forwarded-Host", req.host)
    
    resp = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{host}/agent")
    resp.append(connect)

    logger.info("Telling Twilio to connect to our agent.")
    return web.Response(text=str(resp), content_type="text/xml")

# This is your robot's main mission.
async def entrypoint(ctx: JobContext):
    logger.info(f"Agent is starting up for a new call.")
    await ctx.connect()
    participant = await ctx.wait_for_participant()
    logger.info(f"Connected to: {participant.identity}")

    @function_tool
    async def get_current_time() -> str:
        return f"The current time is {datetime.now().strftime('%I:%M %p')}"

    agent = Agent(
        instructions="You are a friendly and helpful AI assistant.",
        tools=[get_current_time]
    )
    
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3", language="en-US"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(model="sonic-2", voice="a0e99841-438c-4a64-b679-ae501e7d6091")
    )

    await session.start(agent=agent, room=ctx.room)
    
    await session.generate_reply(
        instructions="Say 'Good morning! Thank you for calling. How can I help you today?'"
    )
    logger.info("Agent session is over.")

# This is the main "ON" switch for your robot.
if __name__ == "__main__":
    cli.run_app(
        worker_options=WorkerOptions(
            entrypoint_fnc=entrypoint,
            http_routes=[web.post("/", handle_request)],
        ),
    )