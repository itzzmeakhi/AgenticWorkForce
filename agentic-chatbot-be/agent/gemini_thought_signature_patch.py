"""
Workaround for a confirmed bug in langchain-google-genai==4.4.0 (latest on
PyPI as of 2026-09; no newer release exists yet).

Root cause (read directly from the installed package's source,
chat_models.py's `_parse_chat_history`, ~line 1593-1649): when replaying
message history to a Gemini 3+ model, the library patches a missing
`thought_signature` onto function-call parts so the API's validator
doesn't reject them -- but it does this ONLY for the *first* function_call
part of each model-authored turn:

    first_fc_seen = False
    for part in content_msg.parts or []:
        if part.function_call:
            if not first_fc_seen:          # <-- bug: only patches part #1
                if not part.thought_signature:
                    part.thought_signature = SKIP_THOUGHT_SIGNATURE_VALIDATOR
                first_fc_seen = True

Any turn where the agent calls more than one tool at once (this app's
`agent_node` naturally does this -- e.g. `track_package` + `get_order_status`
in a single AIMessage.tool_calls) leaves the second and later function_call
parts with no thought_signature at all. Gemini then rejects the *next*
request with:

    400 Function call is missing a thought_signature in functionCall parts
    ... function call `default_api:<tool>`, position 2.

There is no config flag to disable Gemini 3's thought_signature requirement,
and no supported `parallel_tool_calls=False` switch in this integration
(bind_tools has no such parameter), so the fix has to be applied at the
message-parsing layer. This module monkeypatches
`langchain_google_genai.chat_models._parse_chat_history` (the sole call
site, `chat_models.py:3823`) to re-run the *same* sentinel-patching logic
the library already uses for the first function call, but for every
function_call part in every model turn, not just the first.

Verified fix (see project notes / commit message): without this patch, a
two-tool-call turn leaves part[1]'s thought_signature as None; with it,
every function_call part gets the 'skip_thought_signature_validator'
sentinel Google's own SDK recognizes as a bypass for replayed history.

Import this module once, before constructing any `ChatGoogleGenerativeAI`
instance (see `agent/llm_provider.py`). It's a no-op if the installed
langchain-google-genai doesn't expose the private symbols it needs (e.g. a
future release that fixes this upstream), so it's safe to always import.
"""
import logging

logger = logging.getLogger(__name__)

_PATCHED = False


def apply():
    global _PATCHED
    if _PATCHED:
        return
    try:
        from langchain_google_genai import chat_models as _cm
    except ImportError:
        return

    original = getattr(_cm, "_parse_chat_history", None)
    skip_sentinel = getattr(_cm, "SKIP_THOUGHT_SIGNATURE_VALIDATOR", None)
    dummy_bytes = getattr(_cm, "DUMMY_THOUGHT_SIGNATURE", None)
    if original is None or skip_sentinel is None:
        logger.warning(
            "gemini_thought_signature_patch: expected internals not found in "
            "installed langchain-google-genai -- skipping (upstream may have "
            "already fixed this, or the package layout changed)."
        )
        return

    def _patch_all_function_call_parts(formatted_messages):
        patched_count = 0
        for content_msg in formatted_messages:
            if getattr(content_msg, "role", None) != "model":
                continue
            for part in getattr(content_msg, "parts", None) or []:
                if not getattr(part, "function_call", None):
                    continue
                if getattr(part, "thought_signature", None):
                    continue
                try:
                    part.thought_signature = skip_sentinel
                except ValueError:
                    part.thought_signature = dummy_bytes
                patched_count += 1
        if patched_count:
            logger.debug(
                "gemini_thought_signature_patch: patched %d function_call part(s) "
                "missing a thought_signature (positions 2+ in multi-tool-call turns).",
                patched_count,
            )

    def patched_parse_chat_history(*args, **kwargs):
        system_instruction, formatted_messages = original(*args, **kwargs)
        _patch_all_function_call_parts(formatted_messages)
        return system_instruction, formatted_messages

    _cm._parse_chat_history = patched_parse_chat_history
    _PATCHED = True
    logger.info(
        "gemini_thought_signature_patch applied: all function_call parts (not "
        "just the first) in a replayed turn now get a thought_signature."
    )
