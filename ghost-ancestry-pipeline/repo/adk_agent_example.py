"""Example ADK agent wiring for this pipeline (adapt to your own agent).

Shows the three settings the pipeline depends on:
  1. all 17 skills loaded with SkillToolset,
  2. a code executor, so run_skill_script can run the scripts on this machine,
  3. the folder layout: run the agent from the working directory that holds
     .agent/skills/ and repo/. This file lives in repo/; the scripts find
     repo/ (config.env, results/, ...) from the working directory, and
     PIPELINE_ROOT is also set here as a safety net.

AGENTS.md is passed through an instruction *function*: ADK does not apply
{placeholder} state templating to instruction functions, and AGENTS.md is
plain text that should reach the model unchanged.

Model: set ADK_MODEL. A plain name (e.g. a Gemini model) is used directly;
"litellm/<provider>/<model>" (e.g. litellm/ollama_chat/my-distilled-model)
goes through LiteLLM, which needs `pip install litellm`.
"""
import os
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.skills import load_skills_from_dir
from google.adk.tools.skill_toolset import SkillToolset

HERE = Path(__file__).resolve().parent          # repo/
WORKDIR = HERE.parent                            # holds .agent/skills and repo
os.environ.setdefault("PIPELINE_ROOT", str(HERE))  # inherited by the scripts

AGENTS_TEXT = (HERE / "AGENTS.md").read_text()

model_name = os.environ.get("ADK_MODEL", "gemini-2.5-flash")
if model_name.startswith("litellm/"):
    from google.adk.models.lite_llm import LiteLlm
    model = LiteLlm(model=model_name[len("litellm/"):])
else:
    model = model_name

skill_toolset = SkillToolset(
    skills=load_skills_from_dir(WORKDIR / ".agent" / "skills"),
    # Runs scripts as local subprocesses with this process's environment.
    # Every pipeline call returns in seconds (long work runs in the
    # background), so the timeout only guards against a stuck call.
    code_executor=UnsafeLocalCodeExecutor(timeout_seconds=600),
)

root_agent = LlmAgent(
    name="ghost_ancestry_agent",
    model=model,
    description="Runs the personal ghost-ancestry pipeline skills in order.",
    instruction=lambda ctx: AGENTS_TEXT,
    tools=[skill_toolset],
)
