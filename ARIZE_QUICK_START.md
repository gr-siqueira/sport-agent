# Arize AX Quick Start Guide

Get started with Arize AX observability in 5 minutes.

## Prerequisites

1. Arize account (sign up at https://app.arize.com)
2. Arize Space ID and API Key

## Setup (3 steps)

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Add to `backend/.env`:

```bash
# Arize Credentials
ARIZE_SPACE_ID=your-space-id-here
ARIZE_API_KEY=your-api-key-here

# LLM Provider (required)
OPENAI_API_KEY=your-openai-key-here
```

Get your credentials:
- Go to https://app.arize.com
- Navigate to **Settings** → **API Keys**
- Copy your **Space ID** and **API Key**

### 3. Start Server

```bash
python main.py
```

You should see:
```
✓ Initializing Arize AX tracing...
✓ Arize AX tracing enabled for project: sport-agent
✓ View traces at: https://app.arize.com/organizations/YOUR_SPACE_ID
```

## Verify It's Working

### Option 1: Run Test Script

```bash
cd backend
python test_arize_tracing.py
```

This will:
- ✓ Check environment variables
- ✓ Verify packages installed
- ✓ Test tracing initialization
- ✓ Generate a test digest with traces

### Option 2: Manual Test

```bash
# 1. Configure test user
curl -X POST http://localhost:8000/configure-interests \
  -H "Content-Type: application/json" \
  -d '{
    "teams": ["Lakers"],
    "leagues": ["NBA"],
    "user_id": "test-user-123"
  }'

# 2. Generate digest (creates traces)
curl -X POST http://localhost:8000/generate-digest \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user-123"}'
```

## View Traces in Arize

1. Go to https://app.arize.com
2. Select your Space
3. Navigate to **Tracing** → **Traces**
4. You should see traces from the digest generation

### What You'll See

**Parallel Agent Execution**:
```
├─ generate_digest (root)
   ├─ schedule_agent (parallel)
   ├─ scores_agent (parallel)
   ├─ player_agent (parallel)
   ├─ analysis_agent (parallel)
   └─ digest_agent (synthesis)
```

**Each span includes**:
- Agent type and role
- User preferences (teams, leagues, players)
- Tool calls with arguments
- LLM prompts and responses
- Execution times
- Token usage

### Filter Traces

Use these filters in Arize:

```
# By user
user.id = "test-user-123"

# By agent
agent.type = "schedule"

# By team
preferences.teams CONTAINS "Lakers"

# Failed requests
output.success = false
```

## Troubleshooting

### No traces appearing?

1. **Check credentials**: Verify `ARIZE_SPACE_ID` and `ARIZE_API_KEY` in `.env`
2. **Check logs**: Look for `✓ Arize AX tracing enabled` at startup
3. **Wait a moment**: Traces may take 10-30 seconds to appear
4. **Check project**: Ensure you're viewing the correct project (`sport-agent`)

### Server won't start?

1. **Missing packages**: Run `pip install -r requirements.txt`
2. **Missing .env**: Create `.env` file in `backend/` directory
3. **Wrong directory**: Make sure you're in `backend/` directory

### Import errors?

```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

## Next Steps

- **Read full guide**: See `ARIZE_AX_SETUP.md` for comprehensive documentation
- **Customize attributes**: Add your own span attributes
- **Monitor production**: Use Arize for production monitoring
- **Set up alerts**: Configure alerts in Arize for errors/latency

## Key Files

- `backend/main.py` - Main application with tracing instrumentation
- `backend/requirements.txt` - Dependencies including Arize packages
- `backend/.env` - Environment variables (create this)
- `ARIZE_AX_SETUP.md` - Comprehensive setup guide
- `backend/test_arize_tracing.py` - Test script

## Support

- **Arize Docs**: https://docs.arize.com
- **Arize AX**: https://www.arize.com/docs/ax
- **Issues**: Check server logs for error messages

## Important Notes

⚠️ **This uses Arize AX (cloud), NOT Phoenix (local)**

✓ **Tracing is optional** - System works without it
✓ **Zero performance impact** - Async trace export
✓ **Graceful degradation** - Missing credentials won't break the app

