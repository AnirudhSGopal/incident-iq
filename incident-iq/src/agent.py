"""
IncidentIQ Strands agent definition.

Run standalone first (before AgentCore deployment):
    python src/agent.py
"""

import json
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from botocore.config import Config
from strands import Agent
from strands.models.bedrock import BedrockModel
from tools.log_cluster import get_clustered_logs

SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.md"


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text()


def build_agent() -> Agent:
    boto_config = Config(
        retries={
            "max_attempts": 3,
            "mode": "adaptive",
        }
    )
    model = BedrockModel(boto_client_config=boto_config)
    return Agent(
        model=model,
        system_prompt=load_system_prompt(),
        tools=[get_clustered_logs],
    )


def _extract_json(text: str) -> str:
    """
    Finds the first valid JSON object in a string, even if it's
    surrounded by conversational text or markdown code fences.
    """
    # Regex to find a JSON object, possibly inside markdown fences
    match = re.search(r"```(json)?\s*(\{.*?\})\s*```|(\{.*?\})", text, re.DOTALL)
    if match:
        # Prioritize the explicitly captured JSON content over the full match
        # Group 2 will be the JSON from the markdown block, group 3 from the raw block
        json_str = match.group(2) or match.group(3)
        if json_str:
            return json_str
    # As a fallback, return the original text if no JSON is found
    return text


def analyze_incident(log_group: str, minutes_back: int = 10) -> str:
    """
    Runs the full pipeline: agent fetches clustered logs via its tool,
    reasons about root cause, and returns the structured JSON answer.
    """
    agent = build_agent()
    prompt = (
        f"Analyze the current incident. Use your tool to fetch clustered logs "
        f"from log group '{log_group}' for the last {minutes_back} minutes, "
        f"then respond with the required JSON output."
    )
    response = agent(prompt)
    return _extract_json(str(response))


if __name__ == "__main__":
    import config
    result = analyze_incident(log_group=config.LOG_GROUP)
    print(result)