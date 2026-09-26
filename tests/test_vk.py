import json

import httpx
import pytest

from app import vk


@pytest.fixture
def mock_vk(monkeypatch):
    calls = []
    real_client = httpx.Client
    monkeypatch.setattr(vk, "REQUEST_INTERVAL", 0)
    monkeypatch.setattr(vk.time, "sleep", lambda _: None)

    def install(handler):
        def transport(request):
            from urllib.parse import parse_qs
            data = {k: values[0] for k, values in parse_qs(request.content.decode()).items()}
            calls.append((request, data))
            return handler(request, data)
        client = real_client(transport=httpx.MockTransport(transport))
        monkeypatch.setattr(vk.httpx, "Client", lambda **kwargs: client)
        return calls
    return install


def payload(items, count=None):
    return httpx.Response(200, json={"response": {"items": items, "count": len(items) if count is None else count}})


def test_vk_uses_post_body_and_preserves_known_edges(mock_vk):
    def handler(request, data):
        assert request.method == "POST"
        assert "access_token" not in str(request.url)
        assert data["access_token"] == "not-a-real-token"
        assert data["v"] == "5.199"
        return payload({"1": [2, 3], "2": [1, 3], "3": [1, 2]}[data["user_id"]])
    calls = mock_vk(handler)
    graph = vk.fetch_vk_graph("1", "not-a-real-token", 2)
    assert len(calls) == 3
    assert len(graph["edges"]) == 3
    assert graph["metadata"]["is_complete"] is True
    assert "not-a-real-token" not in json.dumps(graph)
    assert all("truth" not in n for n in graph["nodes"])


def test_private_profile_and_sampling_are_visible(mock_vk):
    def handler(_, data):
        if data["user_id"] == "1":
            return payload([2, 3], count=20)
        if data["user_id"] == "2":
            return httpx.Response(200, json={"error": {"error_code": 30, "error_msg": "SECRET TOKEN"}})
        return payload([1, 2])
    mock_vk(handler)
    graph = vk.fetch_vk_graph("1", "token", 2)
    assert graph["metadata"]["sampled"] is True
    assert graph["metadata"]["is_complete"] is False
    assert graph["metadata"]["missing_nodes"] == ["2"]
    assert len(graph["edges"]) == 3
    assert "SECRET" not in json.dumps(graph)


def test_pagination_keeps_late_edges(mock_vk, monkeypatch):
    monkeypatch.setattr(vk, "PAGE_SIZE", 2)
    def handler(_, data):
        if data["user_id"] == "1":
            return payload([2, 3])
        if data["user_id"] == "2":
            return payload([1, 88] if data["offset"] == "0" else [3], count=3)
        return payload([1])
    calls = mock_vk(handler)
    graph = vk.fetch_vk_graph("1", "token", 2)
    assert any(data["offset"] == "2" for _, data in calls)
    assert {"source": "2", "target": "3"} in graph["edges"]


def test_rate_limit_retries_then_stops_remaining_nodes(mock_vk):
    def handler(_, data):
        if data["user_id"] == "1":
            return payload([2, 3])
        return httpx.Response(200, json={"error": {"error_code": 6}})
    calls = mock_vk(handler)
    graph = vk.fetch_vk_graph("1", "token", 2)
    assert len(calls) == 4
    assert set(graph["metadata"]["incomplete_nodes"]) == {"2", "3"}
    assert len(graph["edges"]) == 2


def test_network_error_does_not_leak_secret(mock_vk):
    def handler(request, data):
        raise httpx.ReadTimeout("token=TOPSECRET", request=request)
    mock_vk(handler)
    with pytest.raises(ValueError) as exc:
        vk.fetch_vk_graph("1", "TOPSECRET")
    assert "TOPSECRET" not in str(exc.value)


def test_neighbor_scan_cap_is_disclosed(mock_vk, monkeypatch):
    monkeypatch.setattr(vk, "PAGE_SIZE", 2)
    monkeypatch.setattr(vk, "MAX_SCAN_PER_NODE", 2)
    mock_vk(lambda _, data: payload([2]) if data["user_id"] == "1" else payload([1, 90], count=10))
    graph = vk.fetch_vk_graph("1", "token", 1)
    assert graph["metadata"]["incomplete_nodes"] == ["2"]
    assert graph["metadata"]["is_complete"] is False
    assert any("первыми 2" in message for message in graph["metadata"]["warnings"])


def test_empty_ego_is_rejected_with_explanation(mock_vk):
    def handler(request, _):
        if "users.get" in str(request.url):
            return httpx.Response(200, json={"response": [{"id": 1}]})
        return payload([])
    mock_vk(handler)
    with pytest.raises(ValueError, match="пустой список друзей"):
        vk.fetch_vk_graph("1", "token")


def test_http_429_recovers_without_putting_token_in_url(mock_vk):
    requests = 0
    def handler(request, data):
        nonlocal requests
        requests += 1
        if "users.get" in str(request.url):
            return httpx.Response(200, json={"response": [{"id": 1}]})
        return httpx.Response(429) if requests == 1 else payload([])
    mock_vk(handler)
    with pytest.raises(ValueError, match="пустой список друзей"):
        vk.fetch_vk_graph("1", "token")
    assert requests == 3


def test_malformed_remote_payload_is_readable(mock_vk):
    mock_vk(lambda _, data: httpx.Response(200, json={"response": {"items": [True], "count": 1}}))
    with pytest.raises(ValueError, match="некорректный ID"):
        vk.fetch_vk_graph("1", "token")


@pytest.mark.parametrize("code", [5, 14, 27])
def test_authorization_errors_stop_and_hide_response(mock_vk, code):
    mock_vk(lambda _, data: httpx.Response(200, json={"error": {"error_code": code, "error_msg": "SECRET"}}))
    with pytest.raises(ValueError) as exc:
        vk.fetch_vk_graph("1", "SECRET")
    assert "SECRET" not in str(exc.value)


@pytest.mark.parametrize("user,token,limit", [("https://vk.com/id1", "token", 80), ("0", "token", 80),
                                              ("-1", "token", 80), ("1", "", 80), ("1", "token", 81),
                                              ("1", "token", True), ("1", "space token", 10)])
def test_bad_input_without_network(user, token, limit):
    with pytest.raises(ValueError):
        vk.fetch_vk_graph(user, token, limit)
