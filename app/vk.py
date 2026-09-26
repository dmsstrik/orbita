"""VK ego-graph import via the official friends.get API."""

from __future__ import annotations

import re
import time

import httpx

from .ingest import normalize_graph

API_URL = "https://api.vk.com/method/friends.get"
USERS_URL = "https://api.vk.com/method/users.get"
API_VERSION = "5.199"
PAGE_SIZE = 5000
MAX_SCAN_PER_NODE = 10_000
REQUEST_INTERVAL = 0.36
TOTAL_SECONDS = 135


class _VKFailure(Exception):
    def __init__(self, message: str, code: int | None = None, *, fatal: bool = False):
        super().__init__(message)
        self.code = code
        self.fatal = fatal


def users_get(client: httpx.Client, user_id: str) -> dict:
    response = client.post(USERS_URL, data={"access_token": "", "user_ids": user_id, "fields": "deactivated", "v": API_VERSION})
    data = response.json().get("response") or []
    return data[0] if data else {}


def fetch_vk_graph(user_id: str, token: str, max_friends: int = 80) -> dict:
    """Fetch the root account, up to 80 friends and observed links between them."""
    if isinstance(user_id, bool) or not re.fullmatch(r"[1-9][0-9]{0,18}", str(user_id).strip()):
        raise ValueError("Укажите положительный числовой VK ID пользователя, например 123456. Ссылки и короткие имена пока не поддерживаются.")
    root = str(int(str(user_id).strip()))
    if not isinstance(token, str) or not token.strip() or len(token) > 4096 or any(c.isspace() for c in token):
        raise ValueError("Укажите корректный токен VK без пробелов (не более 4096 символов).")
    if isinstance(max_friends, bool) or not isinstance(max_friends, int) or not 1 <= max_friends <= 80:
        raise ValueError("Размер выборки VK должен быть целым числом от 1 до 80 друзей.")
    started = time.monotonic()
    last_request = 0.0
    request_count = 0

    def request_page(client, node_id, offset, count):
        nonlocal last_request, request_count
        for attempt in range(3):
            if time.monotonic() - started >= TOTAL_SECONDS:
                raise _VKFailure("Достигнут лимит времени сбора.")
            delay = REQUEST_INTERVAL - (time.monotonic() - last_request)
            if delay > 0:
                time.sleep(delay)
            try:
                last_request = time.monotonic()
                request_count += 1
                response = client.post(API_URL, data={"access_token": token, "v": API_VERSION,
                                                     "user_id": node_id, "count": count, "offset": offset})
                if response.status_code == 429:
                    if attempt < 2:
                        time.sleep(0.8 * (attempt + 1))
                        continue
                    raise _VKFailure("VK ограничил частоту запросов; повторите сбор позже.", 429)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError, UnicodeError):
                # Response bodies and exception reprs may contain tokens.
                raise _VKFailure("Не удалось получить ответ VK: проверьте соединение и повторите запрос.") from None
            if not isinstance(payload, dict):
                raise _VKFailure("VK вернул ответ неизвестного формата.")
            if "error" in payload:
                error = payload["error"]
                code = error.get("error_code") if isinstance(error, dict) else None
                if not isinstance(code, int):
                    code = None
                if code in (6, 29) and attempt < 2:
                    time.sleep(0.8 * (attempt + 1))
                    continue
                if code in (5, 27, 28):
                    raise _VKFailure("VK отклонил авторизацию. Проверьте токен и его разрешения.", code, fatal=True)
                if code in (15, 18, 30, 200):
                    raise _VKFailure("Список друзей недоступен: профиль закрыт, удалён или прав доступа недостаточно.", code)
                if code in (6, 29):
                    raise _VKFailure("VK ограничил частоту запросов; повторите сбор позже.", code)
                if code == 14:
                    raise _VKFailure("VK запросил проверку CAPTCHA. Автоматический сбор остановлен; повторите позднее.", code, fatal=True)
                raise _VKFailure(f"VK не разрешил запрос (код {code if code is not None else 'неизвестен'}).", code)
            result = payload.get("response")
            if (not isinstance(result, dict) or not isinstance(result.get("items"), list) or
                    not isinstance(result.get("count"), int) or isinstance(result.get("count"), bool) or result["count"] < 0):
                raise _VKFailure("VK вернул некорректный список друзей.")
            ids = []
            for item in result["items"]:
                value = item.get("id") if isinstance(item, dict) else item
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    raise _VKFailure("VK вернул некорректный ID в списке друзей.")
                ids.append(str(value))
            if len(ids) > count or len(ids) > result["count"]:
                raise _VKFailure("VK вернул несогласованное количество записей.")
            return result["count"], ids
        raise _VKFailure("VK ограничил частоту запросов; повторите сбор позже.")

    warnings = []
    missing, incomplete, completed = [], [], []
    edges = set()
    with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False, trust_env=False) as client:
        try:
            root_count, root_items = request_page(client, root, 0, max_friends)
        except _VKFailure as exc:
            raise ValueError(f"Не удалось собрать окружение центрального аккаунта: {exc}") from None
        selected = list(dict.fromkeys(node_id for node_id in root_items if node_id != root))
        if not selected:
            profile = users_get(client, root)
            if profile.get("deactivated"):
                reason = {"deleted": "аккаунт удалён", "banned": "аккаунт заблокирован"}.get(profile["deactivated"], f"аккаунт недоступен ({profile['deactivated']})")
                raise ValueError(f"У аккаунта {root} нет доступных для сбора связей: {reason}.")
            raise ValueError(f"VK вернул пустой список друзей для {root}: список скрыт настройками приватности, аккаунт удалён или друзей нет. Попробуйте другой ID, например 27089.")
        selected_set = set(selected)
        for friend in selected:
            edges.add(tuple(sorted((root, friend))))
        sampled = root_count > len(selected)
        if sampled:
            warnings.append(f"Выборка ограничена: получено {len(selected)} из {root_count} друзей центрального аккаунта.")
        budget_stopped = False
        for friend in selected:
            if budget_stopped or time.monotonic() - started >= TOTAL_SECONDS:
                incomplete.append(friend)
                budget_stopped = True
                continue
            offset = 0
            observed = set()
            expected = None
            changed = False
            try:
                while True:
                    page_count = min(PAGE_SIZE, MAX_SCAN_PER_NODE - offset)
                    total, items = request_page(client, friend, offset, page_count)
                    if expected is not None and total != expected:
                        warnings.append(f"Список друзей {friend} изменился во время сбора; снимок может быть несогласованным.")
                        changed = True
                    expected = total
                    for other in items:
                        if other in selected_set and other != friend:
                            edges.add(tuple(sorted((friend, other))))
                    observed.update(items)
                    offset += len(items)
                    if offset >= total:
                        if len(observed) < total or changed:
                            incomplete.append(friend)
                        else:
                            completed.append(friend)
                        break
                    if not items or offset >= MAX_SCAN_PER_NODE:
                        incomplete.append(friend)
                        if offset >= MAX_SCAN_PER_NODE:
                            warnings.append(f"Аккаунт {friend}: просмотр ограничен первыми {MAX_SCAN_PER_NODE} записями списка друзей.")
                        break
            except _VKFailure as exc:
                if exc.fatal:
                    raise ValueError(str(exc)) from None
                missing.append(friend)
                incomplete.append(friend)
                warnings.append(f"Аккаунт {friend}: {exc}" + (f" Код VK: {exc.code}." if exc.code else ""))
                if exc.code in (6, 29, 429) or time.monotonic() - started >= TOTAL_SECONDS:
                    budget_stopped = True
        if incomplete:
            warnings.append(f"Не завершён сбор списков друзей у {len(set(incomplete))} из {len(selected)} аккаунтов; повторите сбор или используйте готовый полный граф.")
        if budget_stopped:
            warnings.append("Сбор остановлен по лимиту времени или частоты запросов; сохранены наблюдавшиеся связи.")
    return normalize_graph({
        "name": f"VK · окружение {root}",
        "nodes": [{"id": node_id, "label": f"VK {node_id}"} for node_id in [root, *selected]],
        "edges": [list(pair) for pair in sorted(edges)],
        "metadata": {"source": "vk", "root": root, "warnings": warnings,
                     "missing_nodes": missing, "incomplete_nodes": sorted(set(incomplete)),
                     "complete_neighbor_lists": completed, "sampled": sampled,
                     "root_friend_count": root_count, "selected_friend_count": len(selected),
                     "is_complete": not sampled and not incomplete,
                     "edge_semantics": "observed_friendship_only; unavailable_edges_unknown",
                     "max_friends": max_friends, "max_scan_per_node": MAX_SCAN_PER_NODE,
                     "api_version": API_VERSION, "request_count": request_count,
                     "collection_seconds": round(time.monotonic() - started, 2)},
    })
