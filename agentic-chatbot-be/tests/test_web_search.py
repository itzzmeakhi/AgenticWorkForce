"""Tavily web-search tool -- the HTTP call is mocked; no network or key needed."""
import httpx
import pytest

from agent import web_search_tool as ws

PAYLOAD = {
    "answer": "The RBI repo rate is 5.5%.",
    "results": [
        {"title": "RBI policy", "url": "https://rbi.example/policy", "content": "Repo rate   held\nat 5.5 percent. " * 40},
        {"title": "Second", "url": "https://x.example/2", "content": "More."},
    ],
}


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")


def _respond(monkeypatch, status=200, payload=PAYLOAD, capture=None):
    def fake_post(url, **kw):
        if capture is not None:
            capture.update(url=url, **kw)
        return httpx.Response(status, request=httpx.Request("POST", url), json=payload)

    monkeypatch.setattr(ws.httpx, "post", fake_post)


def test_without_a_key_it_says_so_and_makes_no_request(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(ws.httpx, "post", lambda *a, **k: pytest.fail("must not call the network"))
    assert "not set up" in ws.web_search.invoke({"query": "x"})
    assert not ws.web_search_configured()


def test_formats_answer_and_sources(key, monkeypatch):
    _respond(monkeypatch)
    out = ws.web_search.invoke({"query": "repo rate"})
    assert "Summary: The RBI repo rate is 5.5%." in out
    assert "https://rbi.example/policy" in out and "RBI policy" in out
    assert "untrusted" in out                        # prompt-injection guard text
    assert max(len(line) for line in out.splitlines()) < 600   # snippets are trimmed, whitespace collapsed


def test_request_shape_and_bearer_auth(key, monkeypatch):
    seen = {}
    _respond(monkeypatch, capture=seen)
    ws.web_search.invoke({"query": "repo rate", "max_results": 99})
    assert seen["url"] == ws.TAVILY_URL
    assert seen["headers"]["Authorization"] == "Bearer tvly-test"
    assert seen["json"]["query"] == "repo rate" and seen["json"]["max_results"] == ws.MAX_RESULTS_CAP
    assert seen["json"]["include_answer"] is True


def test_max_results_limits_listed_sources(key, monkeypatch):
    _respond(monkeypatch)
    out = ws.web_search.invoke({"query": "q", "max_results": 1})
    assert "rbi.example" in out and "x.example" not in out


@pytest.mark.parametrize("status,text", [(401, "rejected"), (403, "rejected"), (429, "rate-limited")])
def test_api_errors_become_readable_messages(key, monkeypatch, status, text):
    _respond(monkeypatch, status=status)
    assert text in ws.web_search.invoke({"query": "q"})


def test_server_error_and_network_failure_do_not_raise(key, monkeypatch):
    _respond(monkeypatch, status=500)
    assert "failed" in ws.web_search.invoke({"query": "q"})

    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(ws.httpx, "post", boom)
    assert "cannot look that up" in ws.web_search.invoke({"query": "q"})


def test_empty_results(key, monkeypatch):
    _respond(monkeypatch, payload={"results": []})
    assert "no results" in ws.web_search.invoke({"query": "q"})


class TestAgentIntegration:
    def test_tool_is_available_to_signed_out_and_signed_in_agents(self, make_agent):
        assert "web_search" in make_agent().available_tools
        assert "web_search" in make_agent("abc@gmail.com").available_tools

    def test_agent_calls_web_search_for_external_questions(self, make_agent, key, monkeypatch):
        _respond(monkeypatch)
        result = make_agent().chat("Search the web for the latest news about the RBI repo rate")
        assert [tc["tool"] for tc in result["tool_calls"]] == ["web_search"]
        assert "5.5" in result["reply"]

    def test_account_questions_never_go_to_the_web(self, make_agent, key, monkeypatch):
        monkeypatch.setattr(ws.httpx, "post", lambda *a, **k: pytest.fail("account data must not go to the web"))
        result = make_agent("abc@gmail.com").chat("Show me my orders")
        assert [tc["tool"] for tc in result["tool_calls"]] == ["get_my_orders"]

    def test_prompt_tells_the_model_how_to_use_it(self):
        from agent.system_prompt_config import get_system_prompt

        p = get_system_prompt("general", True, None)
        assert "web_search" in p and "untrusted" in p
