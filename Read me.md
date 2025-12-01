# Therapy Chat Demo (Pilot)

## Overview
A low-latency GPT therapy demo application with FastAPI backend and real-time WebSocket streaming. Features text-to-speech playback, light/dark mode, and billing tracking. The frontend displays streaming responses with Time-To-First-Token (TTFT) and full response latency metrics.

## Project Architecture

### Backend (main.py)
- **FastAPI** web framework with WebSocket support
- **OpenAI Chat Completions API** in streaming mode (gpt-4o-mini model)
- **OpenAI TTS API** for voice playback of responses
- Master therapy prompt sent as system message on every request
- Whisper instructions flow (optional second system message for therapist guidance)
- Billing minutes tracking (metadata only - no clinical content stored)
- Endpoints:
  - `GET /` - Serves the chat UI
  - `GET /health` - Health check endpoint
  - `GET /billing-debug` - Debug endpoint for billing records (demo only)
  - `POST /api/tts` - Text-to-speech endpoint for voice playback
  - `WebSocket /ws/chat` - Real-time chat streaming

### Frontend (templates/index.html)
- ChatGPT-style single-page interface
- WebSocket connection for real-time streaming
- Latency metrics display (TTFT and full response time)
- Light/dark mode toggle with localStorage persistence
- "Listen to reply" button for text-to-speech playback
- Typing indicator animation

## Privacy & Logging
- NO clinical content, transcripts, or patient identity stored
- NO full user messages or responses logged
- Only non-clinical metadata logged (session ID, duration)
- Billing records contain only: session_id, duration_seconds, model, timestamp

## Configuration

### Required Secrets
- `OPENAI_API_KEY` - Your OpenAI API key (set this in environment variables; do NOT put the key in README)

### Customization
- Edit `MASTER_THERAPY_PROMPT` in main.py to update the system prompt
- Use `therapist_whisper` parameter in `build_messages()` for session-specific instructions
- TTS voice can be changed in `/api/tts` endpoint (options: alloy, echo, fable, onyx, nova, shimmer)

## Running the App
1. Set `OPENAI_API_KEY` in Replit Secrets
2. Click Run - FastAPI starts on port 5000
3. Visit the URL to see the chat UI
4. Type a message and click Send to see streaming response with latency metrics
5. Click the microphone button to speak your message (uses OpenAI Whisper for transcription)
6. Click "Listen to reply" on any AI response to hear it spoken (uses OpenAI TTS)

## Tech Stack
- Python 3.11
- FastAPI + Uvicorn
- OpenAI Python SDK (Chat Completions + TTS)
- Jinja2 templating
- Vanilla JavaScript (WebSocket API, Fetch API)

## Recent Changes
- 2025-11-30: Added voice input with microphone button (OpenAI Whisper transcription)
- 2025-11-30: Added text-to-speech "Listen to reply" feature (OpenAI TTS)
- 2025-11-30: Added billing minutes tracking with /billing-debug endpoint
- 2025-11-30: Added whisper instructions flow support
- 2025-11-30: Added light/dark mode toggle
- 2025-11-30: Updated to gpt-4o-mini model
- 2025-11-30: Initial project setup with streaming WebSocket chat
