from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
import json
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Arize AX Observability via OpenInference (optional)
try:
    from arize.otel import register
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from openinference.instrumentation.openai import OpenAIInstrumentor
    from openinference.instrumentation.litellm import LiteLLMInstrumentor
    from openinference.instrumentation import using_prompt_template, using_metadata, using_attributes
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    _TRACING = True
except Exception as e:
    print(f"Warning: Tracing libraries not available: {e}")
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
    delivery_time: str = "08:00"
    timezone: str = "America/Sao_Paulo"
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


# Web Search Integration
def _search_web(query: str, max_results: int = 3) -> Optional[str]:
    """Search web for sports information using Tavily or SerpAPI."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    
    if tavily_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=tavily_key)
            response = client.search(query, max_results=max_results)
            if response and response.get("results"):
                # Concatenate top results
                results = []
                for r in response["results"][:max_results]:
                    content = r.get("content", "")
                    if content:
                        results.append(content)
                return " ".join(results) if results else None
        except Exception as e:
            print(f"Tavily search error: {e}")
    
    return None


# Sports API Integration Functions
def _fetch_api_football(endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
    """Fetch from API-Football (free tier: 100 requests/day)."""
    api_key = os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        return None
    
    url = f"https://v3.football.api-sports.io/{endpoint}"
    headers = {"x-apisports-key": api_key}
    
    try:
        response = httpx.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("response"):
                return data
    except Exception as e:
        print(f"API-Football error: {e}")
    
    return None


def _fetch_ergast_f1(endpoint: str) -> Optional[Dict]:
    """Fetch from Ergast F1 API (completely free, no key needed)."""
    url = f"http://ergast.com/api/f1/{endpoint}.json"
    
    try:
        response = httpx.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Ergast F1 error: {e}")
    
    return None


def _fetch_thesportsdb(endpoint: str) -> Optional[Dict]:
    """Fetch from TheSportsDB (free tier available)."""
    api_key = os.getenv("THESPORTSDB_KEY", "3")  # "3" is free test key
    base_url = f"https://www.thesportsdb.com/api/v1/json/{api_key}"
    
    url = f"{base_url}/{endpoint}"
    
    try:
        response = httpx.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"TheSportsDB error: {e}")
    
    return None


# Sport Classification
def _classify_sport(teams: List[str], leagues: List[str]) -> Dict[str, List[str]]:
    """Classify teams/leagues into sport categories."""
    football_keywords = ["FC", "United", "City", "Real", "Barcelona", "Premier League", 
                         "La Liga", "Serie A", "Bundesliga", "Champions League", "Brasileirão",
                         "Brasileirao", "Palmeiras", "Flamengo", "Corinthians", "São Paulo",
                         "Sao Paulo", "Santos", "Athletico", "Internacional", "Grêmio"]
    tennis_keywords = ["ATP", "WTA", "Grand Slam", "Wimbledon", "US Open", "French Open",
                       "Australian Open", "Roland Garros", "Tennis"]
    f1_keywords = ["Formula", "F1", "Grand Prix", "Ferrari", "Mercedes", "Red Bull Racing",
                   "McLaren", "Verstappen", "Hamilton", "Leclerc"]
    
    sports = {"football": [], "tennis": [], "f1": []}
    all_items = teams + leagues
    
    for item in all_items:
        item_lower = item.lower()
        if any(kw.lower() in item_lower for kw in f1_keywords):
            sports["f1"].append(item)
        elif any(kw.lower() in item_lower for kw in tennis_keywords):
            sports["tennis"].append(item)
        elif any(kw.lower() in item_lower for kw in football_keywords):
            sports["football"].append(item)
        else:
            # Default to football for ambiguous cases
            sports["football"].append(item)
    
    return sports


def _get_league_id(league_name: str) -> Optional[int]:
    """Map league names to API-Football IDs."""
    league_map = {
        "premier league": 39,
        "la liga": 140,
        "serie a": 135,
        "bundesliga": 78,
        "ligue 1": 61,
        "champions league": 2,
        "brasileirão": 71,
        "brasileirao": 71,
        "campeonato brasileiro": 71,
    }
    return league_map.get(league_name.lower())


# Sport-Specific Tools (all using LLM fallback pattern for MVP)

# Specialized Tools for Enhanced UX

@tool
def national_team_info(team_name: str = "Brazil") -> str:
    """Get info about national teams (e.g., Brazil, Argentina, etc.)."""
    # Web search is best for national teams (real-time data)
    query = f"{team_name} national football team latest news matches results upcoming games 2024 2025"
    web_result = _search_web(query, max_results=5)
    if web_result:
        return _with_prefix(f"{team_name} National Team", web_result)
    
    # LLM fallback
    instruction = f"Provide latest info about {team_name} national football team: recent matches, upcoming games, and squad news."
    return _llm_fallback(instruction)


@tool
def champions_league_summary() -> str:
    """Get comprehensive Champions League summary: standings, recent results, upcoming matches."""
    # Try web search first (most current)
    query = "UEFA Champions League 2024-25 standings table recent results upcoming matches"
    web_result = _search_web(query, max_results=8)
    if web_result:
        return _with_prefix("Champions League", web_result)
    
    # Try API-Football for today's fixtures
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    
    data = _fetch_api_football("fixtures", {
        "league": "2",  # Champions League ID
        "date": today,
        "season": "2024"
    })
    
    if data and data.get("response"):
        results = []
        for match in data["response"][:5]:
            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            time = match["fixture"]["date"][11:16]
            results.append(f"{home} vs {away} ({time})")
        if results:
            return _compact("Champions League today: " + "; ".join(results), limit=300)
    
    # LLM fallback
    instruction = "Provide Champions League summary: current standings (top 8 teams), recent key results, and upcoming important matches."
    return _llm_fallback(instruction)


@tool
def tennis_player_info(player_name: str, include_ranking: bool = True) -> str:
    """Get tennis player information: recent matches, upcoming tournaments, ranking."""
    # Web search is best for tennis (real-time tournament data)
    query = f"{player_name} tennis latest match results next tournament 2024 2025 ATP WTA ranking"
    web_result = _search_web(query, max_results=5)
    if web_result:
        return _with_prefix(f"{player_name} (Tennis)", web_result)
    
    # LLM fallback
    instruction = f"Provide info about tennis player {player_name}: recent match results, upcoming tournament, current ATP/WTA ranking."
    return _llm_fallback(instruction)


@tool
def brasileirao_summary() -> str:
    """Get Brasileirão (Brazilian league) summary with standings and recent results."""
    # Try API-Football first
    data = _fetch_api_football("standings", {
        "league": "71",  # Brasileirão ID
        "season": "2024"
    })
    
    if data and data.get("response"):
        standings = data["response"][0]["league"]["standings"][0][:8]
        results = []
        for team in standings:
            results.append(f"{team['rank']}. {team['team']['name']} ({team['points']}pts)")
        if results:
            return _compact("Brasileirão 2024: " + "; ".join(results), limit=300)
    
    # Web search fallback
    query = "Brasileirão 2024 tabela classificação resultados recentes"
    web_result = _search_web(query, max_results=5)
    if web_result:
        return _with_prefix("Brasileirão", web_result)
    
    # LLM fallback
    instruction = "Provide Brasileirão 2024 standings (top 8 teams) with points and recent key results."
    return _llm_fallback(instruction)

@tool
def upcoming_games(teams: List[str], date: str = "today") -> str:
    """Get upcoming games for specified teams."""
    teams_str = ", ".join(teams)
    sports = _classify_sport(teams, [])
    
    # Try API-Football for soccer teams
    if sports["football"]:
        for team in sports["football"]:
            data = _fetch_api_football("fixtures", {
                "team": team,
                "next": 3,
                "timezone": "America/Los_Angeles"
            })
            if data and data.get("response"):
                fixtures = data["response"][:3]
                results = []
                for f in fixtures:
                    home = f["teams"]["home"]["name"]
                    away = f["teams"]["away"]["name"]
                    match_date = f["fixture"]["date"][:10]  # Just date
                    venue = f["fixture"]["venue"]["name"]
                    results.append(f"{home} vs {away} at {venue} on {match_date}")
                if results:
                    return _compact("; ".join(results), limit=250)
    
    # Try F1 API for Formula 1
    if sports["f1"]:
        data = _fetch_ergast_f1("current/next")
        if data:
            races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
            if races:
                race = races[0]
                info = f"Next F1: {race['raceName']} at {race['Circuit']['circuitName']}, {race['date']}"
                return _compact(info)
    
    # Fallback to web search
    query = f"upcoming games schedule {teams_str} {date}"
    web_result = _search_web(query)
    if web_result:
        return _with_prefix("Schedule", web_result)
    
    # Final LLM fallback
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
    sports = _classify_sport(teams, [])
    
    # Try API-Football for soccer
    if sports["football"]:
        for team in sports["football"]:
            data = _fetch_api_football("fixtures", {
                "team": team,
                "last": min(lookback_days, 5),
                "status": "FT"
            })
            if data and data.get("response"):
                results = []
                for match in data["response"][:3]:
                    home = match["teams"]["home"]["name"]
                    away = match["teams"]["away"]["name"]
                    score_home = match["goals"]["home"]
                    score_away = match["goals"]["away"]
                    score = f"{score_home}-{score_away}"
                    results.append(f"{home} {score} {away}")
                if results:
                    return _compact("; ".join(results), limit=250)
    
    # Try F1 results
    if sports["f1"]:
        data = _fetch_ergast_f1("current/last/results")
        if data:
            results_data = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
            if results_data:
                race = results_data[0]
                winner = race["Results"][0]["Driver"]
                info = f"Latest F1: {race['raceName']} - Winner: {winner['givenName']} {winner['familyName']}"
                return _compact(info)
    
    # Web search fallback
    query = f"recent results scores {teams_str} last {lookback_days} days"
    web_result = _search_web(query)
    if web_result:
        return _with_prefix("Recent results", web_result)
    
    # LLM fallback
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
    sports = _classify_sport([], leagues)
    
    # Try API-Football for soccer
    if sports["football"]:
        for league in sports["football"]:
            league_id = _get_league_id(league)
            if league_id:
                data = _fetch_api_football("standings", {
                    "league": league_id,
                    "season": 2024
                })
                if data and data.get("response"):
                    standings = data["response"][0]["league"]["standings"][0][:5]
                    results = []
                    for team in standings:
                        results.append(f"{team['rank']}. {team['team']['name']} ({team['points']}pts)")
                    if results:
                        return _compact(f"{league}: " + "; ".join(results), limit=250)
    
    # Try F1 standings
    if sports["f1"]:
        data = _fetch_ergast_f1("current/driverStandings")
        if data:
            standings = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
            if standings:
                drivers = standings[0]["DriverStandings"][:5]
                results = [f"{d['position']}. {d['Driver']['givenName']} {d['Driver']['familyName']} ({d['points']}pts)" 
                          for d in drivers]
                return _compact("F1 Standings: " + "; ".join(results), limit=250)
    
    # Web search fallback
    query = f"current standings table {leagues_str} 2024 2025"
    web_result = _search_web(query)
    if web_result:
        return _with_prefix("Standings", web_result)
    
    # LLM fallback
    instruction = f"Provide current standings/rankings for {leagues_str}."
    return _llm_fallback(instruction)


@tool
def player_news(player_names: List[str]) -> str:
    """Get latest news about specified players."""
    players_str = ", ".join(player_names)
    
    # Web search is best for player news (most current)
    query = f"latest sports news {players_str} today 2024 2025"
    web_result = _search_web(query, max_results=5)
    if web_result:
        return _with_prefix("Player news", web_result)
    
    # LLM fallback
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


# Advanced Analysis Tools (Key Feature #3: Intelligent Analysis)

@tool
def matchup_analysis(team1: str, team2: str) -> str:
    """Analyze matchup between two teams including form, head-to-head, and key players."""
    instruction = (
        f"Analyze the matchup between {team1} vs {team2}. Include: "
        f"1) Recent form (last 5 games), "
        f"2) Head-to-head record this season, "
        f"3) Key player matchups, "
        f"4) Tactical considerations. Keep it brief (200 chars)."
    )
    return _llm_fallback(instruction)


@tool
def playoff_implications(teams: List[str], league: str) -> str:
    """Analyze playoff, relegation, or tournament implications for teams."""
    teams_str = ", ".join(teams)
    instruction = (
        f"For {teams_str} in {league}, analyze: "
        f"1) Current playoff/relegation standing, "
        f"2) What's at stake in upcoming games, "
        f"3) Magic numbers or crucial matches. Brief summary (200 chars)."
    )
    return _llm_fallback(instruction)


@tool
def detect_rivalries(games: str) -> str:
    """Identify rivalry games and their significance."""
    instruction = (
        f"From these games: {games}, identify any rivalry matchups. "
        f"Explain the rivalry's significance and history. Brief (200 chars)."
    )
    return _llm_fallback(instruction)


@tool
def must_watch_games(games: str, user_context: str = "") -> str:
    """Rank and recommend must-watch games based on multiple factors."""
    instruction = (
        f"From these games: {games}, rank the top must-watch games. "
        f"Consider: rivalry, playoff implications, star players, close matchups. "
        f"User context: {user_context}. Provide top 3 with brief reasons (200 chars)."
    )
    return _llm_fallback(instruction)


# State Management
class SportDigestState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_preferences: Dict[str, Any]
    schedule: Optional[str]
    scores: Optional[str]
    player_news: Optional[str]
    analysis: Optional[str]  # NEW: Intelligent analysis output
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
    
    # Enhanced agent metadata and prompt template instrumentation
    with using_attributes(tags=["schedule", "upcoming_games", "agent"]):
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("agent.type", "schedule")
                current_span.set_attribute("agent.name", "schedule_agent")
                current_span.set_attribute("agent.role", "schedule_gatherer")
                current_span.set_attribute("agent.teams_count", len(teams))
                current_span.set_attribute("agent.teams", ",".join(teams) if teams else "none")
                current_span.set_attribute("agent.timezone", timezone)
                current_span.set_attribute("agent.tools_available", str([t.name for t in tools]))
        
        with using_prompt_template(template=prompt_t, variables=vars_, version="v1"):
            res = agent.invoke(messages)
    
    if getattr(res, "tool_calls", None):
        for c in res.tool_calls:
            calls.append({"agent": "schedule", "tool": c["name"], "args": c.get("args", {})})
        
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("agent.tool_calls_count", len(res.tool_calls))
                current_span.set_attribute("agent.tools_used", str([c["name"] for c in res.tool_calls]))
        
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
    
    if _TRACING:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute("agent.output_length", len(out))
            current_span.set_attribute("agent.success", True)

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
    
    with using_attributes(tags=["scores", "results", "agent"]):
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("agent.type", "scores")
                current_span.set_attribute("agent.name", "scores_agent")
                current_span.set_attribute("agent.role", "scores_analyst")
                current_span.set_attribute("agent.teams_count", len(teams))
                current_span.set_attribute("agent.leagues_count", len(leagues))
                current_span.set_attribute("agent.teams", ",".join(teams) if teams else "none")
                current_span.set_attribute("agent.leagues", ",".join(leagues) if leagues else "none")
                current_span.set_attribute("agent.tools_available", str([t.name for t in tools]))
        
        with using_prompt_template(template=prompt_t, variables=vars_, version="v1"):
            res = agent.invoke(messages)
    
    if getattr(res, "tool_calls", None):
        for c in res.tool_calls:
            calls.append({"agent": "scores", "tool": c["name"], "args": c.get("args", {})})
        
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("agent.tool_calls_count", len(res.tool_calls))
                current_span.set_attribute("agent.tools_used", str([c["name"] for c in res.tool_calls]))
        
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
    
    if _TRACING:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute("agent.output_length", len(out))
            current_span.set_attribute("agent.success", True)

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
    
    with using_attributes(tags=["player", "news", "agent"]):
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("agent.type", "player")
                current_span.set_attribute("agent.name", "player_agent")
                current_span.set_attribute("agent.role", "news_reporter")
                current_span.set_attribute("agent.players_count", len(players))
                current_span.set_attribute("agent.teams_count", len(teams))
                current_span.set_attribute("agent.players", ",".join(players) if players else "none")
                current_span.set_attribute("agent.teams", ",".join(teams) if teams else "none")
                current_span.set_attribute("agent.tools_available", str([t.name for t in tools]))
        
        with using_prompt_template(template=prompt_t, variables=vars_, version="v1"):
            res = agent.invoke(messages)
    
    if getattr(res, "tool_calls", None):
        for c in res.tool_calls:
            calls.append({"agent": "player", "tool": c["name"], "args": c.get("args", {})})
        
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("agent.tool_calls_count", len(res.tool_calls))
                current_span.set_attribute("agent.tools_used", str([c["name"] for c in res.tool_calls]))
        
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
    
    if _TRACING:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute("agent.output_length", len(out))
            current_span.set_attribute("agent.success", True)

    return {"messages": [SystemMessage(content=out)], "player_news": out, "tool_calls": calls}


def analysis_agent(state: SportDigestState) -> SportDigestState:
    """Agent that provides intelligent analysis: matchups, implications, rivalries, must-watch games."""
    prefs = state["user_preferences"]
    teams = prefs.get("teams", [])
    leagues = prefs.get("leagues", [])
    schedule_info = state.get("schedule", "")
    scores_info = state.get("scores", "")
    
    prompt_t = (
        "You are a sports analyst providing strategic insights.\n"
        "Analyze upcoming games for these teams: {teams} in leagues: {leagues}.\n"
        "Schedule context: {schedule}\n"
        "Recent results context: {scores}\n"
        "Provide: 1) Key matchup analysis, 2) Playoff/relegation implications, "
        "3) Rivalry games, 4) Must-watch recommendations.\n"
        "Use the analysis tools to provide insights."
    )
    vars_ = {
        "teams": ", ".join(teams),
        "leagues": ", ".join(leagues),
        "schedule": schedule_info[:300],
        "scores": scores_info[:300]
    }
    
    messages = [SystemMessage(content=prompt_t.format(**vars_))]
    tools = [matchup_analysis, playoff_implications, detect_rivalries, must_watch_games]
    agent = llm.bind_tools(tools)
    
    calls: List[Dict[str, Any]] = []
    
    with using_attributes(tags=["analysis", "intelligence", "agent"]):
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("agent.type", "analysis")
                current_span.set_attribute("agent.name", "analysis_agent")
                current_span.set_attribute("agent.role", "sports_analyst")
                current_span.set_attribute("agent.teams_count", len(teams))
                current_span.set_attribute("agent.leagues_count", len(leagues))
                current_span.set_attribute("agent.teams", ",".join(teams) if teams else "none")
                current_span.set_attribute("agent.leagues", ",".join(leagues) if leagues else "none")
                current_span.set_attribute("agent.has_schedule_context", bool(schedule_info))
                current_span.set_attribute("agent.has_scores_context", bool(scores_info))
                current_span.set_attribute("agent.tools_available", str([t.name for t in tools]))
        
        with using_prompt_template(template=prompt_t, variables=vars_, version="v1"):
            res = agent.invoke(messages)
    
    if getattr(res, "tool_calls", None):
        for c in res.tool_calls:
            calls.append({"agent": "analysis", "tool": c["name"], "args": c.get("args", {})})
        
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("agent.tool_calls_count", len(res.tool_calls))
                current_span.set_attribute("agent.tools_used", str([c["name"] for c in res.tool_calls]))
        
        tool_node = ToolNode(tools)
        tr = tool_node.invoke({"messages": [res]})
        
        messages.append(res)
        messages.extend(tr["messages"])
        
        synthesis_prompt = (
            "Synthesize the analysis into key insights: "
            "1) Most important matchups, 2) Playoff implications, "
            "3) Rivalry alerts, 4) Top must-watch games."
        )
        messages.append(SystemMessage(content=synthesis_prompt))
        
        with using_prompt_template(template=synthesis_prompt, variables=vars_, version="v1-synthesis"):
            final_res = llm.invoke(messages)
        out = final_res.content
    else:
        out = res.content
    
    if _TRACING:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute("agent.output_length", len(out))
            current_span.set_attribute("agent.success", True)

    return {"messages": [SystemMessage(content=out)], "analysis": out, "tool_calls": calls}


# Helper Functions for Digest Sections

def _extract_team_info(team_name: str, text: str) -> str:
    """Extract team-specific information from text."""
    if not text or not team_name:
        return ""
    
    # Simple extraction: find sentences containing team name
    sentences = text.split('.')
    relevant = [s.strip() for s in sentences if team_name.lower() in s.lower()]
    return '. '.join(relevant[:2]) + '.' if relevant else ""


def _build_football_section(teams: List[str], leagues: List[str], schedule: str, scores: str, analysis: str) -> str:
    """Build organized football section with teams and leagues."""
    if not teams and not leagues:
        return ""
    
    section = "⚽ **FUTEBOL**\n"
    section += "=" * 70 + "\n\n"
    
    # Individual teams
    for team in teams:
        section += f"### {team}\n"
        
        # Extract team-specific data
        team_schedule = _extract_team_info(team, schedule)
        team_scores = _extract_team_info(team, scores)
        
        if team_scores:
            section += f"📊 Resultados recentes: {team_scores}\n"
        if team_schedule:
            section += f"📅 Próximos jogos: {team_schedule}\n"
        section += "\n"
    
    # Champions League special section
    if any("Champions" in l for l in leagues):
        section += "### 🏆 UEFA Champions League\n"
        cl_info = _extract_team_info("Champions", scores + " " + schedule + " " + analysis)
        if cl_info:
            section += f"{cl_info}\n"
        section += "\n"
    
    # Brasileirão section
    if any("Brasileir" in l for l in leagues):
        section += "### 🇧🇷 Brasileirão\n"
        br_info = _extract_team_info("Brasileir", scores + " " + schedule)
        if br_info:
            section += f"{br_info}\n"
        section += "\n"
    
    return section


def _is_tennis_player(player_name: str) -> bool:
    """Check if a player is a tennis player based on name patterns."""
    tennis_keywords = ["fonseca", "djokovic", "nadal", "federer", "alcaraz", "sinner"]
    return any(kw in player_name.lower() for kw in tennis_keywords)


def _build_tennis_section(players: List[str], player_news: str) -> str:
    """Build tennis section with player info."""
    if not players:
        return ""
    
    section = "🎾 **TÊNIS**\n"
    section += "=" * 70 + "\n\n"
    
    for player in players:
        if _is_tennis_player(player) or "tennis" in player.lower():
            section += f"### {player}\n"
            player_info = _extract_team_info(player, player_news)
            if player_info:
                section += f"{player_info}\n"
            else:
                section += "Informações não disponíveis no momento.\n"
            section += "\n"
    
    return section


def _build_f1_section(schedule: str, scores: str) -> str:
    """Build F1 section with races and standings."""
    # Check if F1 data exists
    if not ("F1" in schedule or "F1" in scores or "Formula" in schedule or "Formula" in scores):
        return ""
    
    section = "🏎️ **FÓRMULA 1**\n"
    section += "=" * 70 + "\n\n"
    
    # Extract F1 info
    f1_schedule = _extract_team_info("F1", schedule) or _extract_team_info("Formula", schedule)
    f1_scores = _extract_team_info("F1", scores) or _extract_team_info("Formula", scores)
    
    if f1_scores:
        section += f"🏁 Última corrida:\n{f1_scores}\n\n"
    
    if f1_schedule:
        section += f"📅 Próxima corrida:\n{f1_schedule}\n\n"
    
    if not f1_scores and not f1_schedule:
        section += "Informações de Fórmula 1 não disponíveis no momento.\n\n"
    
    return section


def digest_agent(state: SportDigestState) -> SportDigestState:
    """Agent that creates sport-specific organized digest."""
    prefs = state["user_preferences"]
    teams = prefs.get("teams", [])
    players = prefs.get("players", [])
    leagues = prefs.get("leagues", [])
    
    # Get data from other agents
    schedule = state.get("schedule", "")
    scores = state.get("scores", "")
    player_news = state.get("player_news", "")
    analysis = state.get("analysis", "")
    
    # Classify sports
    sports = _classify_sport(teams, leagues)
    
    # Build sport-specific sections
    sections = []
    
    # Football Section (includes teams and leagues)
    if sports["football"] or any(l in ["Champions League", "Brasileirão", "Premier League"] for l in leagues):
        football_section = _build_football_section(
            teams=sports["football"] + [t for t in teams if t not in sports["football"] and t not in sports["tennis"] and t not in sports["f1"]],
            leagues=leagues,
            schedule=schedule,
            scores=scores,
            analysis=analysis
        )
        if football_section:
            sections.append(football_section)
    
    # Tennis Section
    tennis_players = [p for p in players if _is_tennis_player(p)]
    if tennis_players or sports["tennis"]:
        tennis_section = _build_tennis_section(
            players=tennis_players,
            player_news=player_news
        )
        if tennis_section:
            sections.append(tennis_section)
    
    # F1 Section
    if sports["f1"] or "F1" in str(teams) or "Formula" in str(teams):
        f1_section = _build_f1_section(
            schedule=schedule,
            scores=scores
        )
        if f1_section:
            sections.append(f1_section)
    
    # If sections were built, combine them
    if sections:
        digest = "\n\n".join(sections)
    else:
        # Fallback to simple format if no sections
        digest = f"📊 RESULTADOS RECENTES\n{scores[:300]}\n\n"
        digest += f"📅 PRÓXIMOS JOGOS\n{schedule[:300]}\n\n"
        digest += f"🗞️ NOTÍCIAS\n{player_news[:300]}"
    
    with using_attributes(tags=["digest", "synthesis", "agent"]):
        if _TRACING:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("agent.type", "digest")
                current_span.set_attribute("agent.name", "digest_agent")
                current_span.set_attribute("agent.role", "digest_synthesizer")
                current_span.set_attribute("agent.has_schedule", bool(schedule))
                current_span.set_attribute("agent.has_scores", bool(scores))
                current_span.set_attribute("agent.has_player_news", bool(player_news))
                current_span.set_attribute("agent.has_analysis", bool(analysis))
                current_span.set_attribute("agent.sections_count", len(sections))
                current_span.set_attribute("agent.digest_length", len(digest))
                current_span.set_attribute("agent.success", True)
    
    return {"messages": [SystemMessage(content=digest)], "final_digest": digest}


def build_graph():
    """Build LangGraph workflow with parallel agent execution."""
    g = StateGraph(SportDigestState)
    g.add_node("schedule_node", schedule_agent)
    g.add_node("scores_node", scores_agent)
    g.add_node("player_node", player_agent)
    g.add_node("analysis_node", analysis_agent)  # NEW: Intelligent analysis
    g.add_node("digest_node", digest_agent)

    # Run all 4 agents in parallel (schedule, scores, player, analysis)
    g.add_edge(START, "schedule_node")
    g.add_edge(START, "scores_node")
    g.add_edge(START, "player_node")
    g.add_edge(START, "analysis_node")  # NEW: Analysis runs in parallel
    
    # All four agents feed into the digest agent
    g.add_edge("schedule_node", "digest_node")
    g.add_edge("scores_node", "digest_node")
    g.add_edge("player_node", "digest_node")
    g.add_edge("analysis_node", "digest_node")  # NEW: Analysis feeds into digest
    
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


# Initialize Arize AX tracing once at startup, not per request
if _TRACING:
    try:
        space_id = os.getenv("ARIZE_SPACE_ID")
        api_key = os.getenv("ARIZE_API_KEY")
        if space_id and api_key:
            print("✓ Initializing Arize AX tracing...")
            
            # Register tracer provider with Arize
            tp = register(
                space_id=space_id,
                api_key=api_key,
                project_name=os.getenv("ARIZE_PROJECT_NAME", "sport-agent"),
                # Endpoint is automatically set to Arize's collector
            )
            
            # Instrument LangChain for agent and chain tracing
            LangChainInstrumentor().instrument(
                tracer_provider=tp,
                include_chains=True,
                include_agents=True,
                include_tools=True,
                skip_dep_check=True
            )
            
            # Instrument OpenAI for LLM call tracing
            OpenAIInstrumentor().instrument(
                tracer_provider=tp,
                skip_dep_check=True
            )
            
            # Instrument LiteLLM as fallback
            LiteLLMInstrumentor().instrument(
                tracer_provider=tp,
                skip_dep_check=True
            )
            
            print(f"✓ Arize AX tracing enabled for project: {os.getenv('ARIZE_PROJECT_NAME', 'sport-agent')}")
            print(f"✓ View traces at: https://app.arize.com/organizations/{space_id}")
        else:
            print("⚠ Arize tracing disabled: ARIZE_SPACE_ID or ARIZE_API_KEY not set")
            _TRACING = False
    except Exception as e:
        print(f"⚠ Failed to initialize Arize tracing: {e}")
        _TRACING = False


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
    
    # Enhanced tracing with comprehensive metadata
    if _TRACING:
        # Extract user preferences for span attributes
        teams = prefs.get("teams", [])
        leagues = prefs.get("leagues", [])
        players = prefs.get("players", [])
        timezone = prefs.get("timezone", "Unknown")
        
        with using_attributes(tags=["digest_generation", "multi_agent"]):
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                # Set comprehensive span attributes for Arize visualization
                current_span.set_attribute("user.id", user_id)
                current_span.set_attribute("session.id", user_id)
                current_span.set_attribute("workflow.type", "multi_agent_digest")
                current_span.set_attribute("workflow.name", "sport_digest_generation")
                current_span.set_attribute("agent.graph", "parallel_execution")
                current_span.set_attribute("preferences.teams", ",".join(teams) if teams else "none")
                current_span.set_attribute("preferences.leagues", ",".join(leagues) if leagues else "none")
                current_span.set_attribute("preferences.players", ",".join(players) if players else "none")
                current_span.set_attribute("preferences.timezone", timezone)
                current_span.set_attribute("preferences.num_teams", len(teams))
                current_span.set_attribute("preferences.num_leagues", len(leagues))
                current_span.set_attribute("preferences.num_players", len(players))
                
            out = graph.invoke(state)
            
            # Add output metrics to span
            if current_span and current_span.is_recording():
                digest = out.get("final_digest", "")
                tool_calls = out.get("tool_calls", [])
                current_span.set_attribute("output.digest_length", len(digest))
                current_span.set_attribute("output.tool_calls_count", len(tool_calls))
                current_span.set_attribute("output.success", True)
                current_span.set_status(Status(StatusCode.OK))
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
