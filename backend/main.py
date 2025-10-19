from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Minimal observability via Arize/OpenInference (optional)
try:
    from arize.otel import register
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from openinference.instrumentation.litellm import LiteLLMInstrumentor
    from openinference.instrumentation import using_prompt_template, using_metadata, using_attributes
    from opentelemetry import trace
    _TRACING = True
except Exception:
    def using_prompt_template(**kwargs):  # type: ignore
        from contextlib import contextmanager
        @contextmanager
        def _noop():
            yield
        return _noop()
    def using_metadata(*args, **kwargs):  # type: ignore
        from contextlib import contextmanager
        @contextmanager
        def _noop():
            yield
        return _noop()
    def using_attributes(*args, **kwargs):  # type: ignore
        from contextlib import contextmanager
        @contextmanager
        def _noop():
            yield
        return _noop()
    _TRACING = False

# LangGraph + LangChain
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict, Annotated
import operator
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

# Storage and Scheduling
from storage import load_preferences, save_preferences, list_all_users, delete_preferences, save_digest_history, get_digest_history
from scheduler import start_scheduler, stop_scheduler, schedule_daily_digest, unschedule_digest, get_scheduled_jobs


class SportPreferencesRequest(BaseModel):
    teams: List[str]
    players: Optional[List[str]] = []
    leagues: List[str]
    delivery_time: str = "07:00"
    timezone: str = "America/Los_Angeles"
    user_id: Optional[str] = None


class DigestResponse(BaseModel):
    digest: str
    generated_at: str
    tool_calls: List[Dict[str, Any]] = []


class DigestRequest(BaseModel):
    user_id: str


def _init_llm():
    # Simple, test-friendly LLM init
    class _Fake:
        def __init__(self):
            pass
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            class _Msg:
                content = "Test sport digest"
                tool_calls: List[Dict[str, Any]] = []
            return _Msg()

    if os.getenv("TEST_MODE"):
        return _Fake()
    if os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7, max_tokens=1500)
    elif os.getenv("OPENROUTER_API_KEY"):
        # Use OpenRouter via OpenAI-compatible client
        return ChatOpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            temperature=0.7,
        )
    else:
        # Require a key unless running tests
        raise ValueError("Please set OPENAI_API_KEY or OPENROUTER_API_KEY in your .env")


llm = _init_llm()


# Helper Functions
def _compact(text: str, limit: int = 200) -> str:
    """Compact text to a maximum length, truncating at word boundaries."""
    if not text:
        return ""
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    truncated = cleaned[:limit]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip(",.;- ")


def _llm_fallback(instruction: str, context: Optional[str] = None) -> str:
    """Use the LLM to generate a response when APIs aren't available.
    
    This ensures tools always return useful information, even without API keys.
    """
    prompt = "Respond with 200 characters or less.\n" + instruction.strip()
    if context:
        prompt += "\nContext:\n" + context.strip()
    response = llm.invoke([
        SystemMessage(content="You are a concise sports information assistant."),
        HumanMessage(content=prompt),
    ])
    return _compact(response.content)


def _with_prefix(prefix: str, summary: str) -> str:
    """Add a prefix to a summary for clarity."""
    text = f"{prefix}: {summary}" if prefix else summary
    return _compact(text)


# Sport-Specific Tools (all using LLM fallback pattern for MVP)

@tool
def upcoming_games(teams: List[str], date: str = "today") -> str:
    """Get upcoming games for specified teams."""
    teams_str = ", ".join(teams)
    instruction = f"List upcoming games for {teams_str} on {date}. Include opponent, time, and TV channel."
    return _llm_fallback(instruction)


@tool
def game_times(games: str, timezone: str = "America/Los_Angeles") -> str:
    """Convert game times to user's timezone."""
    instruction = f"Convert these game times to {timezone} timezone: {games}"
    return _llm_fallback(instruction)


@tool
def tv_schedule(games: str) -> str:
    """Find broadcast information for games."""
    instruction = f"Provide TV channel or streaming service information for: {games}"
    return _llm_fallback(instruction)


@tool
def recent_results(teams: List[str], lookback_days: int = 1) -> str:
    """Get recent game results for teams."""
    teams_str = ", ".join(teams)
    instruction = f"Provide scores and brief highlights for {teams_str} games in the last {lookback_days} day(s)."
    return _llm_fallback(instruction)


@tool
def live_scores(leagues: List[str]) -> str:
    """Get current in-progress games for leagues."""
    leagues_str = ", ".join(leagues)
    instruction = f"List current in-progress games in {leagues_str} with live scores."
    return _llm_fallback(instruction)


@tool
def team_standings(leagues: List[str]) -> str:
    """Get current league standings."""
    leagues_str = ", ".join(leagues)
    instruction = f"Provide current standings/rankings for {leagues_str}."
    return _llm_fallback(instruction)


@tool
def player_news(player_names: List[str]) -> str:
    """Get latest news about specified players."""
    players_str = ", ".join(player_names)
    instruction = f"Provide latest news and updates about {players_str}."
    return _llm_fallback(instruction)


@tool
def injury_updates(teams: List[str]) -> str:
    """Get injury reports for teams."""
    teams_str = ", ".join(teams)
    instruction = f"Provide injury report and return-to-play timelines for {teams_str}."
    return _llm_fallback(instruction)


@tool
def player_stats(player_names: List[str]) -> str:
    """Get recent performance statistics for players."""
    players_str = ", ".join(player_names)
    instruction = f"Provide recent performance stats (last 5 games) for {players_str}."
    return _llm_fallback(instruction)


# State Management
class SportDigestState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_preferences: Dict[str, Any]
    schedule: Optional[str]
    scores: Optional[str]
    player_news: Optional[str]
    final_digest: Optional[str]
    tool_calls: Annotated[List[Dict[str, Any]], operator.add]


# Sport Agents
def schedule_agent(state: SportDigestState) -> SportDigestState:
    """Agent that gathers upcoming game schedules."""
    prefs = state["user_preferences"]
    teams = prefs.get("teams", [])
    timezone = prefs.get("timezone", "America/Los_Angeles")
    
    prompt_t = (
        "You are a sports schedule assistant.\n"
        "Find upcoming games for these teams: {teams}.\n"
        "User timezone: {timezone}.\n"
        "Use tools to get game schedules, times, and broadcast information."
    )
    vars_ = {"teams": ", ".join(teams), "timezone": timezone}
    
    messages = [SystemMessage(content=prompt_t.format(**vars_))]
    tools = [upcoming_games, game_times, tv_schedule]
    agent = llm.bind_tools(tools)
    
    calls: List[Dict[str, Any]] = []
    
    # Agent metadata and prompt template instrumentation
    with using_attributes(tags=["schedule", "upcoming_games"]):
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_attribute("metadata.agent_type", "schedule")
                current_span.set_attribute("metadata.agent_node", "schedule_agent")
        
        with using_prompt_template(template=prompt_t, variables=vars_, version="v1"):
            res = agent.invoke(messages)
    
    if getattr(res, "tool_calls", None):
        for c in res.tool_calls:
            calls.append({"agent": "schedule", "tool": c["name"], "args": c.get("args", {})})
        
        tool_node = ToolNode(tools)
        tr = tool_node.invoke({"messages": [res]})
        
        messages.append(res)
        messages.extend(tr["messages"])
        
        synthesis_prompt = "Based on the schedule information, create a concise summary of today's and upcoming games."
        messages.append(SystemMessage(content=synthesis_prompt))
        
        synthesis_vars = {"teams": ", ".join(teams)}
        with using_prompt_template(template=synthesis_prompt, variables=synthesis_vars, version="v1-synthesis"):
            final_res = llm.invoke(messages)
        out = final_res.content
    else:
        out = res.content

    return {"messages": [SystemMessage(content=out)], "schedule": out, "tool_calls": calls}


def scores_agent(state: SportDigestState) -> SportDigestState:
    """Agent that gathers recent scores and standings."""
    prefs = state["user_preferences"]
    teams = prefs.get("teams", [])
    leagues = prefs.get("leagues", [])
    
    prompt_t = (
        "You are a sports scores analyst.\n"
        "Get recent results for these teams: {teams}.\n"
        "Also check standings in these leagues: {leagues}.\n"
        "Use tools to get scores, live games, and standings."
    )
    vars_ = {"teams": ", ".join(teams), "leagues": ", ".join(leagues)}
    
    messages = [SystemMessage(content=prompt_t.format(**vars_))]
    tools = [recent_results, live_scores, team_standings]
    agent = llm.bind_tools(tools)
    
    calls: List[Dict[str, Any]] = []
    
    with using_attributes(tags=["scores", "results"]):
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_attribute("metadata.agent_type", "scores")
                current_span.set_attribute("metadata.agent_node", "scores_agent")
        
        with using_prompt_template(template=prompt_t, variables=vars_, version="v1"):
            res = agent.invoke(messages)
    
    if getattr(res, "tool_calls", None):
        for c in res.tool_calls:
            calls.append({"agent": "scores", "tool": c["name"], "args": c.get("args", {})})
        
        tool_node = ToolNode(tools)
        tr = tool_node.invoke({"messages": [res]})
        
        messages.append(res)
        messages.extend(tr["messages"])
        
        synthesis_prompt = "Summarize recent scores, highlight key results, and mention current standings."
        messages.append(SystemMessage(content=synthesis_prompt))
        
        with using_prompt_template(template=synthesis_prompt, variables=vars_, version="v1-synthesis"):
            final_res = llm.invoke(messages)
        out = final_res.content
    else:
        out = res.content

    return {"messages": [SystemMessage(content=out)], "scores": out, "tool_calls": calls}


def player_agent(state: SportDigestState) -> SportDigestState:
    """Agent that gathers player news and updates."""
    prefs = state["user_preferences"]
    players = prefs.get("players", [])
    teams = prefs.get("teams", [])
    
    prompt_t = (
        "You are a sports news reporter.\n"
        "Get news and updates for these players: {players}.\n"
        "Also check injury reports for teams: {teams}.\n"
        "Use tools to gather player news, injury updates, and performance stats."
    )
    vars_ = {"players": ", ".join(players) if players else "none", "teams": ", ".join(teams)}
    
    messages = [SystemMessage(content=prompt_t.format(**vars_))]
    tools = [player_news, injury_updates, player_stats]
    agent = llm.bind_tools(tools)
    
    calls: List[Dict[str, Any]] = []
    
    with using_attributes(tags=["player", "news"]):
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_attribute("metadata.agent_type", "player")
                current_span.set_attribute("metadata.agent_node", "player_agent")
        
        with using_prompt_template(template=prompt_t, variables=vars_, version="v1"):
            res = agent.invoke(messages)
    
    if getattr(res, "tool_calls", None):
        for c in res.tool_calls:
            calls.append({"agent": "player", "tool": c["name"], "args": c.get("args", {})})
        
        tool_node = ToolNode(tools)
        tr = tool_node.invoke({"messages": [res]})
        
        messages.append(res)
        messages.extend(tr["messages"])
        
        synthesis_prompt = "Summarize player news, injury updates, and notable performances."
        messages.append(SystemMessage(content=synthesis_prompt))
        
        with using_prompt_template(template=synthesis_prompt, variables=vars_, version="v1-synthesis"):
            final_res = llm.invoke(messages)
        out = final_res.content
    else:
        out = res.content

    return {"messages": [SystemMessage(content=out)], "player_news": out, "tool_calls": calls}


def digest_agent(state: SportDigestState) -> SportDigestState:
    """Agent that synthesizes all information into a formatted digest."""
    prefs = state["user_preferences"]
    teams = prefs.get("teams", [])
    players = prefs.get("players", [])
    
    prompt_parts = [
        "Create a daily sports digest for a fan following:",
        "Teams: {teams}",
        "Players: {players}",
        "",
        "Information gathered:",
        "Schedule: {schedule}",
        "Scores: {scores}",
        "Player News: {player_news}",
        "",
        "Format the digest with clear sections:",
        "1. YESTERDAY'S RESULTS",
        "2. TODAY'S SCHEDULE",
        "3. PLAYER NEWS",
        "",
        "Use emojis and make it engaging but concise."
    ]
    
    prompt_t = "\n".join(prompt_parts)
    vars_ = {
        "teams": ", ".join(teams),
        "players": ", ".join(players) if players else "none",
        "schedule": (state.get("schedule") or "")[:400],
        "scores": (state.get("scores") or "")[:400],
        "player_news": (state.get("player_news") or "")[:400],
    }
    
    with using_attributes(tags=["digest", "synthesis"]):
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_attribute("metadata.agent_type", "digest")
                current_span.set_attribute("metadata.agent_node", "digest_agent")
        
        with using_prompt_template(template=prompt_t, variables=vars_, version="v1"):
            res = llm.invoke([SystemMessage(content=prompt_t.format(**vars_))])
    
    return {"messages": [SystemMessage(content=res.content)], "final_digest": res.content}


def build_graph():
    """Build LangGraph workflow with parallel agent execution."""
    g = StateGraph(SportDigestState)
    g.add_node("schedule_node", schedule_agent)
    g.add_node("scores_node", scores_agent)
    g.add_node("player_node", player_agent)
    g.add_node("digest_node", digest_agent)

    # Run schedule, scores, and player agents in parallel
    g.add_edge(START, "schedule_node")
    g.add_edge(START, "scores_node")
    g.add_edge(START, "player_node")
    
    # All three agents feed into the digest agent
    g.add_edge("schedule_node", "digest_node")
    g.add_edge("scores_node", "digest_node")
    g.add_edge("player_node", "digest_node")
    
    g.add_edge("digest_node", END)

    # Compile without checkpointer to avoid state persistence issues
    return g.compile()


app = FastAPI(title="Sport Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def serve_frontend():
    here = os.path.dirname(__file__)
    path = os.path.join(here, "..", "frontend", "index.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"message": "frontend/index.html not found"}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "sport-agent"}


# Initialize tracing once at startup, not per request
if _TRACING:
    try:
        space_id = os.getenv("ARIZE_SPACE_ID")
        api_key = os.getenv("ARIZE_API_KEY")
        if space_id and api_key:
            tp = register(space_id=space_id, api_key=api_key, project_name="sport-agent")
            LangChainInstrumentor().instrument(tracer_provider=tp, include_chains=True, include_agents=True, include_tools=True)
            LiteLLMInstrumentor().instrument(tracer_provider=tp, skip_dep_check=True)
    except Exception:
        pass


# Startup and Shutdown Events
@app.on_event("startup")
def startup_event():
    """Initialize scheduler on startup."""
    start_scheduler()


@app.on_event("shutdown")
def shutdown_event():
    """Gracefully shutdown scheduler."""
    stop_scheduler()


# API Endpoints
@app.post("/configure-interests")
def configure_interests(req: SportPreferencesRequest):
    """Save user sport preferences and schedule daily digest."""
    user_id = req.user_id or str(uuid.uuid4())
    
    # Save preferences
    prefs_dict = req.model_dump()
    prefs_dict["user_id"] = user_id
    success = save_preferences(user_id, prefs_dict)
    
    if not success:
        raise HTTPException(500, "Failed to save preferences")
    
    # Schedule daily digest
    schedule_daily_digest(user_id, req.delivery_time, req.timezone)
    
    return {"status": "saved", "user_id": user_id, "message": "Preferences saved and digest scheduled"}


@app.post("/generate-digest", response_model=DigestResponse)
def generate_digest(req: DigestRequest):
    """Generate digest on-demand for a user."""
    user_id = req.user_id
    prefs = load_preferences(user_id)
    
    if not prefs:
        raise HTTPException(404, "User not found. Please configure interests first.")
    
    graph = build_graph()
    state = {
        "messages": [],
        "user_preferences": prefs,
        "tool_calls": [],
    }
    
    # Add session and user tracking attributes to the trace
    attrs_kwargs = {"user_id": user_id}
    
    if _TRACING:
        with using_attributes(**attrs_kwargs):
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_attribute("user_id", user_id)
            out = graph.invoke(state)
    else:
        out = graph.invoke(state)
    
    digest = out.get("final_digest", "")
    timestamp = datetime.now().isoformat()
    
    # Save to history
    save_digest_history(user_id, digest, timestamp)
    
    return DigestResponse(
        digest=digest,
        generated_at=timestamp,
        tool_calls=out.get("tool_calls", [])
    )


@app.get("/preferences/{user_id}")
def get_preferences(user_id: str):
    """Retrieve user preferences."""
    prefs = load_preferences(user_id)
    if not prefs:
        raise HTTPException(404, "User not found")
    return prefs


@app.put("/preferences/{user_id}")
def update_preferences(user_id: str, req: SportPreferencesRequest):
    """Update user preferences and reschedule digest."""
    prefs = load_preferences(user_id)
    if not prefs:
        raise HTTPException(404, "User not found")
    
    # Update preferences
    prefs_dict = req.model_dump()
    prefs_dict["user_id"] = user_id
    success = save_preferences(user_id, prefs_dict)
    
    if not success:
        raise HTTPException(500, "Failed to update preferences")
    
    # Reschedule daily digest
    schedule_daily_digest(user_id, req.delivery_time, req.timezone)
    
    return {"status": "updated", "message": "Preferences updated and digest rescheduled"}


@app.delete("/preferences/{user_id}")
def delete_user_preferences(user_id: str):
    """Delete user preferences and unschedule digest."""
    success = delete_preferences(user_id)
    if not success:
        raise HTTPException(404, "User not found")
    
    # Unschedule digest
    unschedule_digest(user_id)
    
    return {"status": "deleted", "message": "User preferences deleted and digest unscheduled"}


@app.get("/digest-history/{user_id}")
def digest_history(user_id: str, limit: int = 10):
    """Get digest history for a user."""
    prefs = load_preferences(user_id)
    if not prefs:
        raise HTTPException(404, "User not found")
    
    history = get_digest_history(user_id, limit)
    return {"user_id": user_id, "history": history}


@app.get("/scheduled-jobs")
def scheduled_jobs():
    """Get list of all scheduled digest jobs."""
    jobs = get_scheduled_jobs()
    return {"jobs": jobs}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
