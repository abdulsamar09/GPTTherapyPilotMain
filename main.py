"""
Low-Latency GPT Therapy Demo (Pilot)
=====================================
Backend + Frontend for a therapy-style GPT pilot application.

Key Features:
- ChatGPT API integration (streaming)
- Master prompt injection (server-side only)
- Whisper instructions flow (optional second system message)
- Security & privacy rules (no clinical content stored)
- Billing minutes tracking (metadata only - duration + session ID)
- Voice feature via /api/tts + "Listen to reply" button

Privacy & Logging Rules:
- NO clinical content, transcripts, or patient identity is stored anywhere
- NO full user messages or responses are logged to the console
- Only non-clinical metadata (e.g., "WebSocket request completed") may be logged
- Billing records contain only duration/session ID, never text content
"""

import os
import json
import time
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from openai import AsyncOpenAI
from pydantic import BaseModel

app = FastAPI(title="Therapy Chat Demo")
templates = Jinja2Templates(directory="templates")

_openai_client = None

def get_openai_client():
    """Singleton pattern for OpenAI client to reuse connections and reduce latency."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI()
    return _openai_client

# =============================================================================
# MASTER PROMPT INJECTION
# =============================================================================
# The master prompt is the main system directive that shapes the AI's behavior.
# It is injected server-side on EVERY OpenAI call and is NEVER sent to the frontend.
# This ensures consistent therapeutic tone and security.

MASTER_THERAPY_PROMPT = """
You are an empathetic, licensed-therapist-style AI assistant.
You respond with warmth, clarity, and psychological insight.
[TODO: real master prompt text will be pasted here later.]
"""

# =============================================================================
# BILLING RECORDS (In-Memory for Demo)
# =============================================================================
# Stores only metadata: session_id, duration_seconds, model
# Does NOT store any clinical content, patient text, or responses
# In production, this would be stored in a secure database

BILLING_RECORDS = []

# =============================================================================
# MESSAGE BUILDING WITH WHISPER SUPPORT
# =============================================================================

def build_messages(patient_text: str, therapist_whisper: str | None = None):
    """
    Build the messages array for OpenAI chat completion.
    
    - Master prompt: Main system directives that define the AI's therapeutic persona.
                     Always included on every call, never exposed to frontend.
    
    - Whisper: Optional, therapist/session-specific system layer.
               Used for real-time guidance or context from a supervising therapist.
               Can be None if not needed for a particular interaction.
    
    - Patient text: The user's message (never logged or stored).
    """
    messages = [
        {"role": "system", "content": MASTER_THERAPY_PROMPT},
    ]
    if therapist_whisper:
        # Whisper = optional second system message for session-specific instructions
        messages.append({"role": "system", "content": therapist_whisper})
    messages.append({"role": "user", "content": patient_text})
    return messages


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Serves the one-page frontend chat interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/billing-debug")
async def billing_debug():
    """
    DEBUG ONLY: Returns billing records for inspection.
    
    WARNING: In production, this endpoint should be:
    - Protected with authentication
    - Restricted to admin users only
    - Possibly moved to an internal dashboard
    - Connected to a proper database instead of in-memory storage
    
    Returns only metadata (session_id, duration, model) - no clinical content.
    """
    return {
        "note": "Debug endpoint - would be secured in production",
        "total_sessions": len(BILLING_RECORDS),
        "records": BILLING_RECORDS
    }


class TTSRequest(BaseModel):
    text: str


from fastapi import UploadFile, File


@app.post("/api/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    """
    Speech-to-Text endpoint for voice input feature.
    
    Uses OpenAI's Whisper API to transcribe user's voice to text.
    The audio is NOT stored or logged - only used for real-time transcription.
    
    Returns: JSON with transcribed text.
    """
    try:
        client = get_openai_client()
        
        # Read audio file content
        audio_content = await audio.read()
        
        # Create a file-like object for OpenAI API
        import io
        audio_file = io.BytesIO(audio_content)
        audio_file.name = audio.filename or "audio.webm"
        
        # Transcribe using Whisper
        transcription = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )
        
        # Note: We intentionally do NOT log the transcribed content
        return {"text": transcription}
        
    except Exception as e:
        error_message = str(e)
        if "api_key" in error_message.lower():
            error_message = "OpenAI API key not configured"
        return Response(
            content=json.dumps({"error": error_message}),
            status_code=500,
            media_type="application/json"
        )


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """
    Text-to-Speech endpoint for the "Listen to reply" feature.
    
    Uses OpenAI's TTS API to convert the assistant's response to audio.
    The text is NOT stored or logged - only used for real-time audio generation.
    
    Returns: Audio bytes (MP3 format) with appropriate Content-Type header.
    """
    try:
        client = get_openai_client()
        
        # Generate speech using OpenAI TTS
        # Using 'alloy' voice - options: alloy, echo, fable, onyx, nova, shimmer
        response = await client.audio.speech.create(
            model="tts-1",
            voice="nova",  # Nova has a warm, conversational tone suitable for therapy
            input=request.text,
            response_format="mp3"
        )
        
        # Get audio bytes
        audio_bytes = response.content
        
        # Return audio with proper content type
        # Note: We intentionally do NOT log the text content
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=response.mp3"}
        )
        
    except Exception as e:
        error_message = str(e)
        if "api_key" in error_message.lower():
            error_message = "OpenAI API key not configured"
        return Response(
            content=json.dumps({"error": error_message}),
            status_code=500,
            media_type="application/json"
        )


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for streaming chat.
    
    Security & Privacy:
    - Patient text is NEVER logged or stored
    - Only metadata (session_id, duration) is recorded for billing
    - The master prompt is injected server-side, never exposed to client
    
    Billing:
    - Each interaction generates a billing record with duration
    - No clinical content is included in billing records
    """
    await websocket.accept()
    
    # Generate unique session ID for tracking (no identity info)
    session_id = str(uuid.uuid4())
    model_name = "gpt-4o-mini"
    
    # Metadata logging only - no clinical content
    print(f"Session {session_id}: WebSocket connection opened")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "user_message":
                # Extract patient text - DO NOT LOG THIS
                patient_text = message.get("text", "")
                # ❌ print(patient_text)  # NEVER log clinical content
                
                # Start timing for billing
                start_time = time.time()
                
                # Build messages with master prompt injection
                # therapist_whisper is None for now - can be added later
                messages = build_messages(patient_text, therapist_whisper=None)
                
                try:
                    client = get_openai_client()
                    stream = await client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        stream=True,
                    )
                    
                    # Stream response chunks to client
                    # ❌ We do NOT accumulate or log the full response
                    async for chunk in stream:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if delta.content:
                                await websocket.send_text(json.dumps({
                                    "type": "chunk",
                                    "text": delta.content
                                }))
                    
                    # Calculate duration for billing
                    end_time = time.time()
                    duration_seconds = end_time - start_time
                    
                    # Record billing metadata ONLY (no clinical content)
                    BILLING_RECORDS.append({
                        "session_id": session_id,
                        "duration_seconds": round(duration_seconds, 2),
                        "model": model_name,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
                    })
                    
                    # Metadata logging only
                    print(f"Session {session_id}: chat completed, duration_seconds={duration_seconds:.2f}")
                    
                    await websocket.send_text(json.dumps({"type": "done"}))
                    
                except Exception as e:
                    error_message = str(e)
                    if "api_key" in error_message.lower():
                        error_message = "OpenAI API key not configured. Please set OPENAI_API_KEY in Replit Secrets."
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "text": error_message
                    }))
                    # Metadata logging only - no clinical content in error
                    print(f"Session {session_id}: request encountered an error")
                    
    except WebSocketDisconnect:
        print(f"Session {session_id}: WebSocket connection closed")
    except Exception as e:
        print(f"Session {session_id}: WebSocket error occurred")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
