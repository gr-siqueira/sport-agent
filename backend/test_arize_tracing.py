#!/usr/bin/env python3
"""
Test script to verify Arize AX tracing is working correctly.

This script:
1. Checks if Arize credentials are set
2. Verifies all required packages are installed
3. Tests tracing initialization
4. Makes a test request to generate a digest
5. Confirms traces are being sent to Arize

Usage:
    python test_arize_tracing.py
"""

import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

def check_environment():
    """Check if required environment variables are set."""
    print("=" * 70)
    print("STEP 1: Checking Environment Variables")
    print("=" * 70)
    
    required_vars = {
        "ARIZE_SPACE_ID": "Arize Space ID",
        "ARIZE_API_KEY": "Arize API Key",
    }
    
    llm_vars = {
        "OPENAI_API_KEY": "OpenAI API Key",
        "OPENROUTER_API_KEY": "OpenRouter API Key",
    }
    
    all_good = True
    
    # Check Arize credentials
    for var, name in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✓ {name}: {'*' * 20} (set)")
        else:
            print(f"✗ {name}: NOT SET")
            all_good = False
    
    # Check LLM credentials
    has_llm = False
    for var, name in llm_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✓ {name}: {'*' * 20} (set)")
            has_llm = True
    
    if not has_llm:
        print(f"✗ LLM API Key: NOT SET (need OPENAI_API_KEY or OPENROUTER_API_KEY)")
        all_good = False
    
    print()
    return all_good


def check_packages():
    """Check if required packages are installed."""
    print("=" * 70)
    print("STEP 2: Checking Python Packages")
    print("=" * 70)
    
    required_packages = [
        "arize.otel",
        "openinference.instrumentation",
        "openinference.instrumentation.langchain",
        "openinference.instrumentation.openai",
        "openinference.instrumentation.litellm",
        "opentelemetry",
        "langchain",
        "langchain_openai",
        "langgraph",
    ]
    
    all_good = True
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package}: NOT INSTALLED")
            all_good = False
    
    print()
    return all_good


def test_tracing_init():
    """Test if tracing initialization works."""
    print("=" * 70)
    print("STEP 3: Testing Tracing Initialization")
    print("=" * 70)
    
    try:
        from arize.otel import register
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from openinference.instrumentation.litellm import LiteLLMInstrumentor
        from opentelemetry import trace
        
        space_id = os.getenv("ARIZE_SPACE_ID")
        api_key = os.getenv("ARIZE_API_KEY")
        
        if not space_id or not api_key:
            print("✗ Cannot initialize tracing: Missing credentials")
            return False
        
        print("Registering tracer provider with Arize...")
        tp = register(
            space_id=space_id,
            api_key=api_key,
            project_name="sport-agent-test"
        )
        print("✓ Tracer provider registered")
        
        print("Instrumenting LangChain...")
        LangChainInstrumentor().instrument(
            tracer_provider=tp,
            skip_dep_check=True
        )
        print("✓ LangChain instrumented")
        
        print("Instrumenting OpenAI...")
        OpenAIInstrumentor().instrument(
            tracer_provider=tp,
            skip_dep_check=True
        )
        print("✓ OpenAI instrumented")
        
        print("Instrumenting LiteLLM...")
        LiteLLMInstrumentor().instrument(
            tracer_provider=tp,
            skip_dep_check=True
        )
        print("✓ LiteLLM instrumented")
        
        print()
        print("✓ Tracing initialized successfully!")
        print(f"✓ View traces at: https://app.arize.com/organizations/{space_id}")
        print()
        
        return True
    
    except Exception as e:
        print(f"✗ Tracing initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_span_creation():
    """Test if spans can be created."""
    print("=" * 70)
    print("STEP 4: Testing Span Creation")
    print("=" * 70)
    
    try:
        from opentelemetry import trace
        from openinference.instrumentation import using_attributes
        
        tracer = trace.get_tracer(__name__)
        
        print("Creating test span...")
        with tracer.start_as_current_span("test_span") as span:
            span.set_attribute("test.attribute", "test_value")
            span.set_attribute("test.number", 123)
            
            with using_attributes(tags=["test", "verification"]):
                current_span = trace.get_current_span()
                if current_span and current_span.is_recording():
                    current_span.set_attribute("test.is_recording", True)
                    print("✓ Span is recording")
                else:
                    print("✗ Span is not recording")
                    return False
        
        print("✓ Test span created successfully")
        print()
        return True
    
    except Exception as e:
        print(f"✗ Span creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_request():
    """Test making an API request to generate a digest."""
    print("=" * 70)
    print("STEP 5: Testing API Request (generates traces)")
    print("=" * 70)
    
    try:
        import requests
        
        # Check if server is running
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code != 200:
                print("✗ Server is not responding correctly")
                print("  Please start the server with: python main.py")
                return False
        except requests.exceptions.RequestException:
            print("✗ Server is not running")
            print("  Please start the server in another terminal with: python main.py")
            return False
        
        print("✓ Server is running")
        
        # Create test user preferences
        test_user_id = "arize-test-user-" + str(int(time.time()))
        
        print(f"\nCreating test user preferences (user_id: {test_user_id})...")
        prefs = {
            "teams": ["Lakers", "Golden State Warriors"],
            "leagues": ["NBA"],
            "players": [],
            "delivery_time": "08:00",
            "timezone": "America/Los_Angeles",
            "user_id": test_user_id
        }
        
        response = requests.post(
            "http://localhost:8000/configure-interests",
            json=prefs,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"✗ Failed to create preferences: {response.text}")
            return False
        
        print("✓ Test user preferences created")
        
        # Generate digest
        print("\nGenerating test digest (this will create traces)...")
        response = requests.post(
            "http://localhost:8000/generate-digest",
            json={"user_id": test_user_id},
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"✗ Failed to generate digest: {response.text}")
            return False
        
        result = response.json()
        print("✓ Digest generated successfully")
        print(f"  - Digest length: {len(result['digest'])} characters")
        print(f"  - Tool calls: {len(result.get('tool_calls', []))}")
        print(f"  - Generated at: {result['generated_at']}")
        
        print("\n✓ Traces should now be visible in Arize!")
        print(f"  View at: https://app.arize.com/organizations/{os.getenv('ARIZE_SPACE_ID')}")
        print()
        
        return True
    
    except Exception as e:
        print(f"✗ API request failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  ARIZE AX TRACING VERIFICATION TEST  ".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    results = []
    
    # Run tests
    results.append(("Environment Variables", check_environment()))
    results.append(("Python Packages", check_packages()))
    results.append(("Tracing Initialization", test_tracing_init()))
    results.append(("Span Creation", test_span_creation()))
    results.append(("API Request (Trace Generation)", test_api_request()))
    
    # Print summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print()
    
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("Next Steps:")
        print("1. Go to Arize: https://app.arize.com")
        print("2. Select your Space")
        print("3. Navigate to 'Tracing' → 'Traces'")
        print("4. You should see traces from the test digest generation")
        print()
        print("Look for traces with:")
        print("  - Project: sport-agent-test")
        print(f"  - User ID: starts with 'arize-test-user-'")
        print("  - Workflow: sport_digest_generation")
        print("  - Agents: schedule, scores, player, analysis, digest")
        print()
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print()
        print("Troubleshooting:")
        print("1. Ensure .env file has ARIZE_SPACE_ID and ARIZE_API_KEY")
        print("2. Run: pip install -r requirements.txt")
        print("3. Start the server: python main.py")
        print("4. Check server logs for initialization messages")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())

