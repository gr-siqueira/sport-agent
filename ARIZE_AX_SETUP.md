# Arize AX Observability Setup Guide

This guide explains how to set up and use Arize AX (NOT Phoenix) for observability and tracing in the Sport Agent system.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Instrumentation Details](#instrumentation-details)
6. [Viewing Traces](#viewing-traces)
7. [Troubleshooting](#troubleshooting)

## Overview

The Sport Agent system is instrumented with **Arize AX** observability to provide comprehensive tracing of:

- **Multi-Agent Execution**: Track parallel execution of 4 agents (schedule, scores, player, analysis)
- **LLM Calls**: Monitor all OpenAI/LiteLLM API calls with prompts and responses
- **Tool Calls**: Trace every tool invocation with arguments and results
- **User Context**: Track user preferences, teams, leagues, and players
- **Performance Metrics**: Monitor response times, token usage, and success rates

### Key Features

✓ **Parallel Agent Visualization**: See all 4 agents executing simultaneously  
✓ **Prompt Template Versioning**: Track prompt changes with versioned templates  
✓ **Comprehensive Metadata**: Rich span attributes for filtering and analysis  
✓ **Zero Performance Impact**: Non-blocking trace export  
✓ **Graceful Degradation**: System works without tracing enabled  

## Prerequisites

1. **Arize Account**: Sign up at [https://app.arize.com](https://app.arize.com)
2. **Arize Space**: Create a space in your Arize account
3. **API Credentials**: Obtain your Space ID and API Key

### Getting Arize Credentials

1. Log into your Arize account: https://app.arize.com
2. Navigate to **Settings** → **API Keys**
3. Copy your **Space ID** (format: `ABC123`)
4. Generate or copy your **API Key** (format: `XXXXXXXXXX`)

## Installation

### 1. Install Dependencies

The required packages are already in `requirements.txt`:

```bash
cd backend
pip install -r requirements.txt
```

Key packages installed:
- `arize-otel>=0.8.1` - Arize OpenTelemetry integration
- `openinference-instrumentation>=0.1.12` - Base instrumentation
- `openinference-instrumentation-langchain>=0.1.19` - LangChain tracing
- `openinference-instrumentation-openai>=0.1.14` - OpenAI tracing
- `openinference-instrumentation-litellm>=0.1.0` - LiteLLM tracing
- `openinference-semantic-conventions>=0.1.9` - Semantic conventions

### 2. Set Environment Variables

Create or update your `.env` file in the `backend/` directory:

```bash
# Arize AX Credentials (REQUIRED for tracing)
ARIZE_SPACE_ID=your-space-id-here
ARIZE_API_KEY=your-api-key-here
ARIZE_PROJECT_NAME=sport-agent  # Optional, defaults to "sport-agent"

# LLM Provider (REQUIRED)
OPENAI_API_KEY=your-openai-key-here
# OR
OPENROUTER_API_KEY=your-openrouter-key-here
OPENROUTER_MODEL=openai/gpt-4o-mini  # Optional

# Optional API Keys (for enhanced features)
TAVILY_API_KEY=your-tavily-key  # For web search
API_FOOTBALL_KEY=your-api-football-key  # For live sports data
```

### 3. Verify Installation

Start the server to verify tracing initialization:

```bash
cd backend
python main.py
```

You should see:
```
✓ Initializing Arize AX tracing...
✓ Arize AX tracing enabled for project: sport-agent
✓ View traces at: https://app.arize.com/organizations/YOUR_SPACE_ID
```

If you see warnings:
```
⚠ Arize tracing disabled: ARIZE_SPACE_ID or ARIZE_API_KEY not set
```
Check your `.env` file and ensure credentials are correct.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARIZE_SPACE_ID` | Yes | None | Your Arize Space ID |
| `ARIZE_API_KEY` | Yes | None | Your Arize API Key |
| `ARIZE_PROJECT_NAME` | No | `sport-agent` | Project name in Arize |

### Tracing Initialization

Tracing is initialized **once at module level** in `backend/main.py` (lines 1071-1115):

```python
# Initialize Arize AX tracing once at startup, not per request
if _TRACING:
    tp = register(
        space_id=space_id,
        api_key=api_key,
        project_name=os.getenv("ARIZE_PROJECT_NAME", "sport-agent"),
    )
    
    # Instrument LangChain, OpenAI, and LiteLLM
    LangChainInstrumentor().instrument(tracer_provider=tp, ...)
    OpenAIInstrumentor().instrument(tracer_provider=tp, ...)
    LiteLLMInstrumentor().instrument(tracer_provider=tp, ...)
```

⚠️ **Important**: Never initialize tracing inside request handlers - this causes duplicate traces!

## Instrumentation Details

### 1. Multi-Agent Workflow Tracing

The system traces the entire multi-agent graph execution with parallel agent visualization:

**Root Span Attributes** (set in `/generate-digest` endpoint):
- `user.id` - User identifier
- `session.id` - Session identifier (using user_id)
- `workflow.type` - Type of workflow (`multi_agent_digest`)
- `workflow.name` - Workflow name (`sport_digest_generation`)
- `agent.graph` - Graph structure (`parallel_execution`)
- `preferences.*` - User preferences (teams, leagues, players, timezone)
- `output.*` - Output metrics (digest length, tool call count)

### 2. Individual Agent Tracing

Each agent (schedule, scores, player, analysis, digest) is traced with:

**Agent Span Attributes**:
- `agent.type` - Agent type (e.g., `schedule`, `scores`)
- `agent.name` - Agent function name (e.g., `schedule_agent`)
- `agent.role` - Agent role (e.g., `schedule_gatherer`, `scores_analyst`)
- `agent.teams_count` - Number of teams being tracked
- `agent.leagues_count` - Number of leagues being tracked
- `agent.tools_available` - List of available tools
- `agent.tool_calls_count` - Number of tool calls made
- `agent.tools_used` - List of tools actually used
- `agent.output_length` - Length of agent output
- `agent.success` - Whether agent succeeded

### 3. Prompt Template Versioning

All prompts are tracked with versioning using `using_prompt_template()`:

```python
with using_prompt_template(
    template=prompt_t,
    variables=vars_,
    version="v1"
):
    res = agent.invoke(messages)
```

This enables:
- Prompt version comparison in Arize
- A/B testing of prompts
- Regression detection

### 4. Tool Call Tracing

LangChain's `ToolNode` is automatically instrumented, capturing:
- Tool name
- Tool arguments
- Tool results
- Execution time
- Errors (if any)

### 5. LLM Call Tracing

OpenAI and LiteLLM instrumentors capture:
- Model name
- Prompt content
- Response content
- Token counts (prompt, completion, total)
- Latency
- Cost estimates

## Viewing Traces

### 1. Access Arize Dashboard

Navigate to: `https://app.arize.com/organizations/YOUR_SPACE_ID`

Or use the link printed at server startup.

### 2. Select Your Project

1. In Arize, select the project name (default: `sport-agent`)
2. Navigate to **Tracing** → **Traces**

### 3. Visualize Multi-Agent Execution

You'll see traces with:

**Timeline View**: Shows parallel execution of agents
```
├─ generate_digest (root span)
   ├─ schedule_agent (parallel)
   │  ├─ upcoming_games tool
   │  └─ ChatOpenAI LLM call
   ├─ scores_agent (parallel)
   │  ├─ recent_results tool
   │  └─ ChatOpenAI LLM call
   ├─ player_agent (parallel)
   │  ├─ player_news tool
   │  └─ ChatOpenAI LLM call
   ├─ analysis_agent (parallel)
   │  ├─ matchup_analysis tool
   │  └─ ChatOpenAI LLM call
   └─ digest_agent (synthesis)
      └─ ChatOpenAI LLM call
```

### 4. Filter and Analyze

Use span attributes to filter traces:

**Filter by User**:
```
user.id = "test-user-123"
```

**Filter by Agent**:
```
agent.type = "schedule"
```

**Filter by Teams**:
```
preferences.teams CONTAINS "Lakers"
```

**Find Failed Requests**:
```
output.success = false
```

### 5. Inspect Details

Click on any span to see:
- **Attributes**: All metadata (user, agent, preferences)
- **Events**: Tool calls, LLM calls
- **Prompts**: Full prompt templates with variables
- **Responses**: LLM responses
- **Timing**: Execution time per component

## Troubleshooting

### Tracing Not Working

**Issue**: No traces appearing in Arize

**Solutions**:
1. Verify environment variables are set correctly
2. Check server logs for initialization messages
3. Ensure firewall allows outbound HTTPS to Arize
4. Verify Space ID and API Key are correct
5. Check if tracing is enabled: look for `✓ Arize AX tracing enabled` message

### Duplicate Traces

**Issue**: Multiple traces for single request

**Cause**: Tracing initialized multiple times (in request handler)

**Solution**: Ensure tracing is initialized only once at module level (lines 1071-1115 in `main.py`)

### Missing Spans

**Issue**: Some agents or tools not appearing in traces

**Solutions**:
1. Check if agent has `using_attributes()` context manager
2. Verify `if _TRACING:` block is present
3. Ensure span is recording: `current_span.is_recording()`
4. Check for exceptions in agent code

### High Latency

**Issue**: Tracing adding latency to requests

**Note**: Arize uses async export - traces are sent in background. If experiencing latency:
1. Check network connectivity to Arize
2. Verify you're not in DEBUG mode (extra logging)
3. Consider reducing span attributes if thousands per request

### Environment Variables Not Loading

**Issue**: `.env` file not being read

**Solutions**:
1. Ensure `.env` is in `backend/` directory (same as `main.py`)
2. Verify `python-dotenv` is installed: `pip install python-dotenv`
3. Check `.env` format (no quotes around values, no spaces around `=`)
4. Restart server after changing `.env`

### Traces Not Showing Prompt Content

**Issue**: Can't see full prompts in traces

**Solution**: 
1. Ensure you're using `using_prompt_template()` context manager
2. Check that prompts are under size limits (large prompts may be truncated)
3. Verify `OpenAIInstrumentor` is instrumented

## Advanced Usage

### Custom Span Attributes

Add custom attributes to spans:

```python
from opentelemetry import trace

if _TRACING:
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute("custom.my_metric", 123)
        current_span.set_attribute("custom.my_tag", "value")
```

### Tags and Metadata

Use `using_attributes()` for high-level categorization:

```python
with using_attributes(
    tags=["production", "priority:high"],
    user_id=user_id,
    team="lakers"
):
    # Your code here
```

### Error Tracking

Mark spans as failed:

```python
from opentelemetry.trace import Status, StatusCode

if _TRACING:
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_status(Status(StatusCode.ERROR))
        current_span.set_attribute("error.message", str(e))
```

### Disable Tracing for Testing

Set `TEST_MODE=1` to disable tracing:

```bash
TEST_MODE=1 python main.py
```

Or remove `ARIZE_SPACE_ID` from `.env`.

## Best Practices

### 1. Always Check if Tracing is Enabled

```python
if _TRACING:
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        # Add span attributes
```

### 2. Use Consistent Naming Conventions

- Agent types: lowercase (e.g., `schedule`, `scores`)
- Agent names: snake_case with `_agent` suffix (e.g., `schedule_agent`)
- Span attribute keys: dot notation (e.g., `agent.type`, `user.id`)

### 3. Add Context Early

Set user and session attributes at the root span (in endpoint):

```python
with using_attributes(user_id=user_id, session_id=session_id):
    result = graph.invoke(state)
```

### 4. Version Your Prompts

Always include version in `using_prompt_template()`:

```python
with using_prompt_template(template=prompt, variables=vars_, version="v2"):
    response = llm.invoke(messages)
```

### 5. Track Outputs

Add output metrics to spans:

```python
current_span.set_attribute("output.length", len(result))
current_span.set_attribute("output.tool_calls", len(tool_calls))
current_span.set_attribute("output.success", True)
```

## Support and Resources

- **Arize Documentation**: https://docs.arize.com/arize/llm-large-language-models/llm-traces
- **Arize AX Tracing Guide**: https://www.arize.com/docs/ax/llm-tracing
- **OpenInference Specs**: https://github.com/Arize-ai/openinference
- **LangChain Instrumentation**: https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-langchain

## Changelog

### Version 1.0 (October 2025)
- ✓ Integrated Arize AX (NOT Phoenix)
- ✓ Added comprehensive span attributes for all agents
- ✓ Implemented prompt template versioning
- ✓ Added user context tracking
- ✓ Instrumented OpenAI, LangChain, and LiteLLM
- ✓ Parallel agent execution visualization
- ✓ Graceful degradation when tracing disabled

---

**Note**: This system uses **Arize AX**, which is different from Arize Phoenix (local observability). Arize AX is a cloud-based production observability platform with enterprise features, team collaboration, and long-term trace retention.

