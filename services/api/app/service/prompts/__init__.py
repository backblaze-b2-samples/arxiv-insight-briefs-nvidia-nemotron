"""Prompt strings — kept out of the runtime layer for easy iteration.

All prompts treat arxiv content as untrusted user data (see SECURITY.md).
"""

from app.service.prompts.ranker import RANKER_SYSTEM, build_ranker_user
from app.service.prompts.router import ROUTER_SYSTEM, build_router_user
from app.service.prompts.synthesis import SYNTHESIS_SYSTEM, build_synthesis_user

__all__ = [
    "RANKER_SYSTEM",
    "ROUTER_SYSTEM",
    "SYNTHESIS_SYSTEM",
    "build_ranker_user",
    "build_router_user",
    "build_synthesis_user",
]
