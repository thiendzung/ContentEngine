from app.modules.harness.runtime import ToolRequest, request_fingerprint


def test_tool_request_fingerprint_includes_tool_identity_and_stable_payload() -> None:
    payload_a = {"query": "synthetic", "options": {"locale": "en", "limit": 5}}
    payload_b = {"options": {"limit": 5, "locale": "en"}, "query": "synthetic"}

    search = ToolRequest(tool_key="search", payload=payload_a)
    search_same = ToolRequest(tool_key="search", payload=payload_b)
    reader = ToolRequest(tool_key="reader", payload=payload_a)

    assert request_fingerprint(search) == request_fingerprint(search_same)
    assert request_fingerprint(search) != request_fingerprint(reader)
