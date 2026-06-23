from langchain.agents import create_agent

from app.infrastructure.ai.prompts import SYSTEM_PROMPT


def create_database_agent(model, tools):
    return create_agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT)
