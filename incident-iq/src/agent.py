"""
IncidentIQ Strands agent definition.

Run standalone first (before AgentCore deployment):
    python src/agent.py
"""

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
    return str(response)


if __name__ == "__main__":
    import config
    result = analyze_incident(log_group=config.LOG_GROUP)
    print(result)

