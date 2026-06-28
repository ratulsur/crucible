# Crucible

**Voice-driven mock interviews with a VP-level GenAI interviewer.**

You sit across from a 20-year veteran who has worked abroad across several
multinationals and now runs Generative AI as a VP at a tech giant. She's warm —
and relentless. You talk; she listens, presses, and at the end hands you a candid,
structured assessment of where you stand and exactly what to practice next.

Built for one person's serious practice: a real multi-agent system on LangGraph,
full speech in and out, and a one-command deploy.

![architecture](docs/architecture.png)

---

## What's inside

- **Voice in / voice out** — speak your answers, hear the interviewer reply.
- **A five-agent interview** — strategist, interviewer, evaluator, pacing
  controller, coach. See [`agents/AGENTS.md`](agents/AGENTS.md).
- **Adaptive pressure** — `gentle → standard → hard → brutal`; pacing advances
  phases based on how you're doing.
- **Structured feedback** — recommendation, competency bars, strengths, gaps,
  action items, and model answers for your weakest moments.
- **Records kept** — finished interviews saved to SQLite for review.
- **Provider-flexible** — Claude or OpenAI for the agents; OpenAI for audio.

## Quick start (local)

```bash
cd Interviewer_APP            # this folder
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then fill in your keys
#   ANTHROPIC_API_KEY=...     (agents — recommended)
#   OPENAI_API_KEY=...        (audio; also works as the LLM fallback)

uvicorn app.main:app --reload
# open http://localhost:8000
```

Pick a role, focus areas, your interviewer, and how hard she should press — then
**Begin interview**. Tap to answer, tap when you're done, and end whenever you
like to get the report.

> No `OPENAI_API_KEY`? The app still runs — the web client falls back to your
> browser's built-in speech recognition and synthesis. For real voice quality and
> the persona's voice, set the OpenAI key.

## Deploy to Railway

1. Push this folder to a GitHub repo.
2. In Railway: **New Project → Deploy from GitHub repo** (the `Dockerfile` and
   `railway.toml` are detected automatically).
3. Add variables under **Variables**:
   - `ANTHROPIC_API_KEY` (agents)
   - `OPENAI_API_KEY` (audio)
   - optional: `CRUCIBLE_ACCESS_TOKEN` to gate the API with a shared secret
4. Railway sets `PORT` and exposes the URL. The health check hits `/api/health`.

```bash
# or with the Railway CLI
railway up
```

## Configuration

All via environment variables — see [`.env.example`](.env.example). Highlights:

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | LLM for the agents (preferred) |
| `OPENAI_API_KEY` | — | Audio (STT/TTS); LLM fallback |
| `LLM_PROVIDER` | `auto` | `auto` \| `anthropic` \| `openai` |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | reasoning model |
| `TTS_MODEL` | `gpt-4o-mini-tts` | persona voice |
| `STT_MODEL` | `gpt-4o-transcribe` | transcription |
| `CRUCIBLE_ACCESS_TOKEN` | — | optional API gate (`x-access-token` header) |

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/session/start` | begin; returns the opening question |
| `POST /api/session/answer` | submit a transcribed answer; returns the next question |
| `POST /api/session/end` | finish; returns the structured report |
| `POST /api/stt` | audio → text |
| `POST /api/tts` | text → mp3 (persona voice) |
| `GET /api/sessions` | past interview records |
| `GET /api/health` | status + capabilities |

## Layout

```
app/
  main.py        FastAPI app + endpoints
  graph.py       LangGraph wiring (checkpointed, per-turn)
  agents/        strategist · interviewer · evaluator · pacing · coach
  persona.py     the interviewer's character + TTS voice
  state.py       interview state + structured output models
  audio.py       STT / TTS (OpenAI)
  llm.py         provider factory (Claude / OpenAI)
  store.py       session config + SQLite records
web/             the voice interview room (HTML/CSS/JS)
docs/            architecture diagram
```

## Notes

- Single-user by design. Interview state lives in an in-memory checkpointer
  (resets on redeploy); completed runs persist to SQLite. For multi-replica use,
  swap `MemorySaver` for a persistent LangGraph checkpointer.
- Microphone access needs HTTPS (Railway gives you that) or `localhost`.
