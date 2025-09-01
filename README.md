# AI Trip Planner

A fast, intelligent trip planning application powered by LangGraph and Groq with comprehensive Arize observability.

## 🚀 Performance & Observability

- **LLM Providers**: Works with OpenAI or Groq (choose via env)
- **Clear Tracing**: Chain/agent/tool spans visible in Arize
- **Prompt Metadata**: Templates + variables logged on LLM spans (using `using_prompt_template`)
- **Deterministic Flow**: Sequential orchestration for reliable data handoff between agents

## Architecture

### Frontend (React + TypeScript)
- Modern Material-UI interface
- Real-time trip planning requests
- Error handling and loading states

### Backend (FastAPI + LangGraph)
- **Sequential Workflow**:
  - Research agent → Budget agent → Local Experiences agent → Itinerary synthesis
- **Single LLM per helper**: Helpers make one LLM call to choose tools; synthesis happens in itinerary
- **Arize Tracing**: OpenInference auto-instrumentation; prompt templates recorded on LLM spans

## 📊 Observability with Arize

This application includes comprehensive tracing using Arize, allowing you to:
- **Visualize Agent Workflows**: See the complete LangGraph execution flow
- **Monitor LLM Calls**: Track all LLM interactions with latency and token usage
- **Trace Prompt Templates**: Version and monitor all prompt templates
- **Debug Errors**: Quickly identify and fix issues in your agent pipeline
- **Analyze Performance**: Identify bottlenecks and optimize agent performance

### Setting Up Arize Tracing

1. **Get Arize Credentials**:
   - Sign up at [https://app.arize.com](https://app.arize.com)
   - Navigate to your Space Settings
   - Copy your Space ID and API Key

2. **Configure Environment**:
   Add to your `.env` file:
   ```bash
   ARIZE_SPACE_ID=your_space_id_here
   ARIZE_API_KEY=your_api_key_here
   ```

3. **View Traces**:
   - Run your application
   - Navigate to [https://app.arize.com](https://app.arize.com)
   - Select your project (e.g., "ai-trip-planner")
   - View real-time traces of your agent execution

## 📋 Data Labeling with Airtable

The application supports exporting traces to Airtable for manual labeling and evaluation. This allows you to:
- **Label Quality**: Mark trip plans as excellent, good, or poor
- **Label Accuracy**: Assess accuracy of recommendations
- **Add Notes**: Document specific issues or highlights
- **Run Evaluations**: Analyze labeled data for model improvements

### Setting Up Airtable Integration

1. **Create Airtable Base**:
   - Sign up at [https://airtable.com](https://airtable.com)
   - Create a new base for your trip planner traces
   - Note your Base ID from the URL: `airtable.com/appXXXXXXXXXXXXXX`

2. **Get API Key**:
   - Go to [https://airtable.com/account](https://airtable.com/account)
   - Generate a personal access token with write permissions

3. **Configure Environment**:
   Add to your `.env` file:
   ```bash
   AIRTABLE_API_KEY=your_airtable_api_key_here
   AIRTABLE_BASE_ID=your_airtable_base_id_here
   AIRTABLE_TABLE_NAME=trip_planner_traces  # or your preferred table name
   ```
   
   **⚠️ Important**: When creating your Airtable Personal Access Token, you MUST:
   - Add the required scopes: `data.records:read` and `data.records:write`
   - **Add your base to the token's Access list** (this is often missed!)
   - See `backend/FIX_AIRTABLE_PERMISSIONS.md` if you get 403 errors

4. **Required Table Fields**:
   The table will need these fields (created automatically on first write):
   - `trace_id` (Single line text)
   - `destination` (Single line text)
   - `quality` (Single select: excellent, good, poor)
   - `accuracy` (Single select: accurate, mostly_accurate, inaccurate)
   - `notes` (Long text)
   - `labeled_by` (Single line text)
   - Plus automated fields for request/response data

### Using the Labeling API

#### Get Unlabeled Traces
```bash
GET /traces/unlabeled?limit=100
```

#### Update Labels
```bash
POST /traces/{record_id}/label
{
  "human_label_quality": "excellent",
  "human_label_accuracy": "accurate",
  "human_label_notes": "Great recommendations for temples",
  "labeled_by": "reviewer@example.com"
}
```

#### Export Labeled Data for Evaluation
```bash
GET /evaluation/export
```

#### Run Evaluation Script
```bash
cd backend
python evaluate_traces.py
```

This generates:
- Evaluation report with quality/accuracy distributions
- CSV export of all labeled traces
- JSON file with detailed metrics
- Tool usage statistics

## Quick Start

### 1. Setup Environment

Create a `.env` file in the `backend/` directory:

```bash
# Required: Groq API Key (get from https://console.groq.com)
GROQ_API_KEY=your_groq_api_key_here

# Required: Arize observability (get from https://app.arize.com)
ARIZE_SPACE_ID=your_arize_space_id_here
ARIZE_API_KEY=your_arize_api_key_here

# Optional: For web search capabilities
TAVILY_API_KEY=your_tavily_api_key

# Optional: Fallback to OpenAI if Groq unavailable
OPENAI_API_KEY=your_openai_api_key
```

### 2. Install Dependencies

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend  
cd ../frontend
npm install
```

### 3. Run the Application

```bash
# Start both services
./start.sh

# Or run separately:
# Backend (canonical): cd backend && python main_with_tools_fixed.py
# Frontend: cd frontend && npm start
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Arize Traces: https://app.arize.com (select your project)

## Performance Optimizations

### ⚡ Groq Integration
- **10x faster inference** compared to OpenAI
- Uses `llama-3.1-70b-versatile` model for optimal speed/quality balance
- 30-second timeout with 2000 max tokens

### 🔄 Orchestration
- Sequential agent execution (research → budget → local → itinerary)
- Ensures itinerary has complete upstream context

### 📊 Arize Observability Features
- **LangGraph Instrumentation**: Automatic tracing of all graph nodes and edges
- **LLM Call Tracking**: Monitor all ChatOpenAI and LiteLLM calls
- **Prompt Template Versioning**: Track prompt evolution with versions
- **Error Tracing**: Capture and analyze exceptions with full context
- **Performance Metrics**: Latency, token usage, and success rates

## API Endpoints

### POST `/plan-trip`
Creates a comprehensive trip plan.

**Request:**
```json
{
  "destination": "Tokyo, Japan",
  "duration": "7 days", 
  "budget": "$2000",
  "interests": "food, culture, temples",
  "travel_style": "cultural"
}
```

**Response:**
```json
{
  "result": "# 7-Day Tokyo Cultural Experience\n\n## Day 1: Arrival and Asakusa District..."
}
```

### GET `/health`
Health check endpoint.

## Development

### Graph Structure
```
START → Research → Budget → Local Experiences → Itinerary → END
```

### Key Components
- `research_node()`: Destination research and weather analysis
- `budget_node()`: Cost breakdown and money-saving tips  
- `local_experiences_node()`: Authentic local recommendations
- `itinerary_node()`: Day-by-day planning with all data

### Prompt Templates
- Templates and variables are attached to LLM spans via `using_prompt_template`.
- Each agent uses a versioned template (e.g., `v1`).

### Tracing Spans
- Chain/agent/tool spans from LangChain/LiteLLM; LLM spans include prompt metadata.

## Synthetic Evals (Bad Tools & Tone)

Use the focused generator to provoke bad tool calls and detect tone issues for frustrated users:

```bash
python generate_bad_tool_calls.py \
  --base-url http://localhost:8000 \
  --count 20 \
  --outfile synthetic_bad_tool_calls.json
```

The JSON report includes:
- `eval_tools`: wrong tools used, missing recommended tools
- `eval_tone`: `tone_off` flag with reasons (empathy, acknowledgement, cheerfulness, dismissiveness)

## Troubleshooting

### Common Issues
1. **Slow responses**: Ensure you're using Groq API key, not OpenAI
2. **Empty results**: Check API key configuration in `.env`
3. **Graph errors**: Verify all dependencies are installed correctly
4. **No traces in Arize**: Verify ARIZE_SPACE_ID and ARIZE_API_KEY are set correctly

### Monitoring Best Practices
- Use Arize to monitor prompt performance over time
- Set up alerts for high latency or error rates
- Review trace waterfalls to identify bottlenecks
- Use prompt template versions to A/B test improvements

## Tech Stack

- **Frontend**: React, TypeScript, Material-UI, Axios
- **Backend**: FastAPI, LangGraph, LangChain, Groq, LiteLLM
- **Observability**: Arize, OpenInference, OpenTelemetry
- **Infrastructure**: Docker, Docker Compose
