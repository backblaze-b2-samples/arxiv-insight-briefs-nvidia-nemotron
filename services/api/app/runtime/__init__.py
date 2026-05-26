"""Runtime layer — FastAPI route modules. No business logic.

Layer rule: only imports from service/, types/, config/. Never imports repo/
or external SDKs directly.
"""
