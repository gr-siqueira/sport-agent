# Sport Agent

A **production-ready multi-agent system** for personalized daily sports digests. This system demonstrates three essential AI engineering patterns that can be studied, modified, and adapted for other use cases.

## What You'll Learn

- 🤖 **Multi-Agent Orchestration**: 4 specialized agents running in parallel using LangGraph
- 📅 **Automated Scheduling**: Daily digest generation at user-configured times
- 💾 **Persistent Storage**: JSON-based user preference management
- 📊 **Observability**: Production tracing with Arize for debugging and evaluation
- 🛠️ **Composable Architecture**: Easily adapt from "sport agent" to your own agent system

**Perfect for:** Developers learning to build, evaluate, and deploy agentic AI systems with scheduling and state management.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       User Preferences                           │
│              (teams, players, leagues, delivery time)            │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   FastAPI Endpoint      │
                    │   + JSON Storage        │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   LangGraph Workflow    │
                    │   (Parallel Execution)  │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────▼─────┐           ┌─────▼──────┐         ┌──────▼─────┐
   │ Schedule │           │   Scores   │         │   Player   │
   │  Agent   │           │   Agent    │         │   Agent    │
   └────┬─────┘           └─────┬──────┘         └──────┬─────┘
        │                        │                        │
        │ Tools:                 │ Tools:                 │ Tools:
        │ • upcoming_games       │ • recent_results       │ • player_news
        │ • game_times           │ • live_scores          │ • injury_updates
        │ • tv_schedule          │ • team_standings       │ • player_stats
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                            ┌────▼─────┐
                            │  Digest  │
                            │  Agent   │
                            │(Synthesis)│
                            └────┬─────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Daily Sport Digest    │
                    │   + Scheduled Delivery  │
                    └─────────────────────────┘

All agents, tools, and LLM calls → Arize AX Observability
```

## 🔍 Observability with Arize AX

This system includes comprehensive **Arize AX** (NOT Phoenix) observability for production monitoring and debugging:

### What's Traced
- ✅ **Multi-Agent Execution**: Visualize parallel agent execution with detailed timelines
- ✅ **LLM Calls**: All prompts, responses, token usage, and latency
- ✅ **Tool Calls**: Every tool invocation with arguments and results
- ✅ **User Context**: Track teams, leagues, players, and preferences
- ✅ **Prompt Versioning**: Version and compare prompt templates

### Quick Setup

1. **Get Arize Credentials** (sign up at https://app.arize.com)
2. **Add to `.env`**:
   ```bash
   ARIZE_SPACE_ID=your-space-id
   ARIZE_API_KEY=your-api-key
   ```
3. **Start Server** - Tracing auto-enabled!
4. **View Traces** at https://app.arize.com

See [`ARIZE_QUICK_START.md`](ARIZE_QUICK_START.md) for detailed setup or [`ARIZE_AX_SETUP.md`](ARIZE_AX_SETUP.md) for comprehensive documentation.

### Test Tracing

```bash
cd backend
python test_arize_tracing.py
```

**Note**: Tracing is optional - system works perfectly without it!

## Key Features

### 🎯 User Configuration
- Select favorite teams across multiple sports
- Follow specific players for personalized updates
- Choose leagues/sports of interest
- Configure delivery time and timezone
- Persistent JSON storage

### 📊 Daily Digest Generation
- **Yesterday's Results**: Scores and highlights for followed teams
- **Today's Schedule**: Upcoming games with times and broadcast info
- **Player News**: Injuries, transfers, and performance updates
- **Standings**: Current league positions

### ⏰ Automated Scheduling
- Daily digest generation at user-specified time
- APScheduler for reliable job scheduling
- Timezone-aware delivery
- Digest history tracking (last 30 digests)

### 🔧 Graceful Degradation
- All tools work without external API keys
- LLM fallback for all sport information
- No API rate limits or costs for MVP
- Future-ready for real sports API integration

## Quickstart

### 1) Requirements
- Python 3.10+ 
- OpenAI API key or OpenRouter API key

### 2) Configure environment
Create `backend/.env` file:
```bash
# Required - LLM Provider (choose one)
OPENAI_API_KEY=your_openai_api_key_here
# OR
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional - Arize AX Observability (recommended)
ARIZE_SPACE_ID=your_arize_space_id
ARIZE_API_KEY=your_arize_api_key
ARIZE_PROJECT_NAME=sport-agent
```

### 3) Install dependencies
```bash
cd backend
pip install -r requirements.txt
# Recommended: Use uv for faster installs
# curl -LsSf https://astral.sh/uv/install.sh | sh
# uv pip install -r requirements.txt
```

### 4) Run
```bash
# From the backend directory
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Or from the root directory
./start.sh
```

### 5) Open
- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Usage

### Via Web Interface
1. Open http://localhost:8000
2. Enter your favorite teams (e.g., "Lakers, Manchester United, Patriots")
3. Optionally add players (e.g., "LeBron James, Cristiano Ronaldo")
4. Select leagues (e.g., "NBA, Premier League, NFL")
5. Choose delivery time and timezone
6. Click "Save Preferences"
7. Click "Generate Digest Now" to see a preview
8. Your digest will be automatically generated daily at your chosen time

### Via API

**Configure Interests:**
```bash
curl -X POST http://localhost:8000/configure-interests \
  -H "Content-Type: application/json" \
  -d '{
    "teams": ["Lakers", "Manchester United"],
    "players": ["LeBron James"],
    "leagues": ["NBA", "Premier League"],
    "delivery_time": "07:00",
    "timezone": "America/Los_Angeles"
  }'
```

**Generate Digest On-Demand:**
```bash
curl -X POST http://localhost:8000/generate-digest \
  -H "Content-Type: application/json" \
  -d '{"user_id": "your-user-id"}'
```

**Get Preferences:**
```bash
curl http://localhost:8000/preferences/{user_id}
```

**Get Digest History:**
```bash
curl http://localhost:8000/digest-history/{user_id}?limit=10
```

## Project Structure

```
├── backend/
│   ├── main.py                 # FastAPI app, agents, tools, endpoints
│   ├── storage.py              # JSON-based user preferences storage
│   ├── scheduler.py            # APScheduler for daily digest automation
│   ├── requirements.txt        # Python dependencies
│   ├── data/
│   │   └── user_preferences.json  # Persistent user data
│   └── .env                    # Environment variables (gitignored)
├── frontend/
│   └── index.html              # Web UI for configuration and viewing
├── test scripts/
│   └── test_api.py             # API testing script
├── README.md                   # This file
├── .cursorrules                # Development guidelines
└── start.sh                    # Quick start script
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve web UI |
| GET | `/health` | Health check |
| POST | `/configure-interests` | Save user preferences and schedule digest |
| POST | `/generate-digest` | Generate digest on-demand |
| GET | `/preferences/{user_id}` | Get user preferences |
| PUT | `/preferences/{user_id}` | Update user preferences |
| DELETE | `/preferences/{user_id}` | Delete user preferences |
| GET | `/digest-history/{user_id}` | Get digest history |
| GET | `/scheduled-jobs` | List all scheduled jobs |

## Development

### Agent Architecture

The system uses 4 specialized agents:

**1. Schedule Agent**
- Gathers upcoming game schedules
- Converts times to user's timezone
- Finds broadcast information
- Tools: `upcoming_games`, `game_times`, `tv_schedule`

**2. Scores Agent**
- Retrieves recent game results
- Checks live scores
- Gets league standings
- Tools: `recent_results`, `live_scores`, `team_standings`

**3. Player Agent**
- Collects player news and updates
- Reports on injuries
- Tracks player statistics
- Tools: `player_news`, `injury_updates`, `player_stats`

**4. Digest Agent**
- Synthesizes all information
- Formats into readable sections
- Creates engaging morning briefing

### Parallel Execution

The first three agents run **in parallel** (not sequentially) for maximum performance. They all converge into the Digest Agent for final synthesis.

```python
# Parallel execution pattern
g.add_edge(START, "schedule_node")
g.add_edge(START, "scores_node")
g.add_edge(START, "player_node")

# Converge for synthesis
g.add_edge("schedule_node", "digest_node")
g.add_edge("scores_node", "digest_node")
g.add_edge("player_node", "digest_node")
```

### Adding New Features

**To add a new sport tool:**
```python
@tool
def new_sport_tool(param: str) -> str:
    """Clear description of what this tool does."""
    instruction = f"Generate information about {param}."
    return _llm_fallback(instruction)
```

**To add a new agent:**
1. Define agent function following existing patterns
2. Add node to graph in `build_graph()`
3. Configure edges for parallel or sequential execution
4. Update `SportDigestState` TypedDict if needed

## Scheduling System

The Sport Agent uses APScheduler to automate daily digest generation:

- **Configuration**: Users set delivery time and timezone
- **Persistence**: Schedules persist across server restarts
- **Reliability**: Background scheduler handles job execution
- **Storage**: Generated digests saved to user's history

### How It Works

1. User configures preferences via web UI or API
2. System schedules daily job at specified time
3. Scheduler triggers `generate_and_send_digest()` function
4. Digest is generated using full LangGraph workflow
5. Result is saved to user's digest history
6. Future: Will send via email/SMS

## Storage System

User preferences and digest history are stored in JSON:

```json
{
  "users": {
    "user-id-123": {
      "teams": ["Lakers", "Manchester United"],
      "players": ["LeBron James"],
      "leagues": ["NBA", "Premier League"],
      "delivery_time": "07:00",
      "timezone": "America/Los_Angeles",
      "digest_history": [
        {
          "digest": "...",
          "timestamp": "2025-10-19T07:00:00"
        }
      ]
    }
  }
}
```

## Performance Metrics

- **Average response time**: ~6-8 seconds
- **Parallel agent execution**: 3 agents simultaneously
- **State management**: Efficient TypedDict with operator.add
- **Storage**: Fast JSON file operations with thread safety

## Observability

When Arize credentials are configured, all operations are traced:

- Agent executions and timings
- Tool calls with arguments
- LLM token usage
- Error tracking
- User attribution

View traces at: https://app.arize.com

## Testing

### Manual Testing
```bash
# Health check
curl http://localhost:8000/health

# Test full workflow
python "test scripts/test_api.py"
```

### Test Mode
Set `TEST_MODE=1` in `.env` to use fake LLM for fast testing without API calls.

## Troubleshooting

**Issue**: Empty or error responses
- **Solution**: Verify `OPENAI_API_KEY` or `OPENROUTER_API_KEY` is set in `backend/.env`

**Issue**: Digest not generating at scheduled time
- **Solution**: Check server logs, ensure server is running continuously

**Issue**: Port already in use
- **Solution**: Stop other services on port 8000 or change port: `uvicorn main:app --port 8001`

**Issue**: Preferences not saving
- **Solution**: Check `backend/data/` directory exists and is writable

## Future Enhancements

### Phase 2: Real API Integration
- ESPN API for live scores and schedules
- SportsData API for comprehensive statistics
- Real-time updates instead of LLM generation

### Phase 3: Notification System
- Email delivery via SendGrid
- SMS delivery via Twilio
- Push notifications via Firebase

### Phase 4: Advanced Features
- Multi-language support
- Fantasy sports integration
- Betting odds and predictions
- Social sharing capabilities

## Adapting to Other Domains

This architecture can be transformed into other agent systems:

**Example Transformations:**
- **Sport Agent** → **News Digest Agent** (tech news, finance, etc.)
- **Sport Agent** → **Weather & Travel Agent**
- **Sport Agent** → **Stock Market Agent**
- **Sport Agent** → **Content Monitoring Agent**

Key patterns to maintain:
- Parallel agent execution
- Graceful degradation
- Persistent storage
- Scheduled automation
- Observability

## License & Credits

Built on the AI Trip Planner architecture, demonstrating multi-agent systems with LangGraph.

Core Technologies:
- **LangGraph 0.2.55+**: Multi-agent orchestration
- **LangChain 0.3.7+**: Agent framework
- **FastAPI**: REST API
- **APScheduler**: Job scheduling
- **OpenAI GPT**: LLM intelligence
- **Arize OTEL**: Observability

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review `.cursorrules` for development patterns
3. Examine existing agent and tool implementations
4. Check Arize traces for debugging

---

**Version**: 1.0.0  
**Status**: Production Ready (MVP)  
**Last Updated**: October 19, 2025
