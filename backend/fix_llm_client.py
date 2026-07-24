import re

with open("D:\\GENAI\\backend\\app\\llm_client.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add _is_generation_failure
func_str = '''
def _is_generation_failure(exc: Exception) -> bool:
    """Return True if the error is a Groq function calling failure (failed_generation)."""
    from openai import APIError
    if isinstance(exc, APIError):
        msg = str(exc).lower()
        return "failed to call a function" in msg or "failed_generation" in msg
    return False
'''

content = content.replace("def _is_rate_limit_or_quota(exc: Exception) -> bool:", func_str + "\ndef _is_rate_limit_or_quota(exc: Exception) -> bool:")

# Update the try/except block around stream
mid_exc_replace = '''
        except Exception as mid_exc:
            # Mid-stream error (quota hit after connection opened)
            if _is_rate_limit_or_quota(mid_exc):
                log.warning(
                    "LLM API mid-stream rate-limit (%s) → circuit + local fallback",
                    type(mid_exc).__name__,
                )
                _llm_cb.record_failure()
                async for event in _stream_local(messages, settings, tools=tools):
                    yield event
                return
            if _is_generation_failure(mid_exc):
                log.warning("LLM API generation failure (tool schema issue) → local fallback")
                async for event in _stream_local(messages, settings, tools=tools):
                    yield event
                return
            raise
'''
content = content.replace('''        except Exception as mid_exc:
            # Mid-stream error (quota hit after connection opened)
            if _is_rate_limit_or_quota(mid_exc):
                log.warning(
                    "LLM API mid-stream rate-limit (%s) → circuit + local fallback",
                    type(mid_exc).__name__,
                )
                _llm_cb.record_failure()
                async for event in _stream_local(messages, settings, tools=tools):
                    yield event
                return
            raise''', mid_exc_replace)

outer_exc_replace = '''
    except Exception as exc:
        if _is_generation_failure(exc):
            log.warning("LLM API generation failure (tool schema issue) → local fallback")
            async for event in _stream_local(messages, settings, tools=tools):
                yield event
            return
            
        log.exception("Unexpected LLM API error: %s", exc)
        if _is_circuit_trippable(exc):
            _llm_cb.record_failure()
        raise
'''
content = content.replace('''    except Exception as exc:
        log.exception("Unexpected LLM API error: %s", exc)
        if _is_circuit_trippable(exc):
            _llm_cb.record_failure()
        raise''', outer_exc_replace)

with open("D:\\GENAI\\backend\\app\\llm_client.py", "w", encoding="utf-8") as f:
    f.write(content)
