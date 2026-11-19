"""Worker ratings: versioned reviews independent of order completion and money."""
from copy import deepcopy
import json
from typing import Any

from fastapi import HTTPException


def _api():
    from app import app_orders_api
    return app_orders_api


def _text(value: Any, *, required: bool = False) -> str:
    api = _api()
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Причина должна быть текстом")
    try:
        text = api.bounded_text(value, "reason", max_length=1000, required=required)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if required and len(text) < 5:
        raise HTTPException(status_code=422, detail="Укажите причину подробнее: не менее 5 символов")
    return text


def _version(review: dict) -> int:
    return int(review.get("revision") or 1)


def _request_id(value: Any) -> str:
    api = _api()
    try:
        return api.bounded_text(value, "request_id", max_length=120, required=True)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _expected_version(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HTTPException(status_code=422, detail="Некорректная версия оценки")
    return value


def _now() -> str:
    api = _api()
    return api.serialize_datetime(api.utc_now())


def _contribution(review: dict) -> tuple[int, int, int]:
    result = review.get("result")
    if result == "void":
        return 0, 0, 0
    rules = _api().WORKER_RESULT_DELTAS
    if result not in rules:
        raise HTTPException(status_code=409, detail="Старая оценка требует отдельной проверки")
    return (
        int(review.get("rating_delta", rules[result])),
        int(result in {"success", "excellent"}),
        int(result == "fail"),
    )


def _change_balance(connection: Any, worker_id: str, old: dict, new: dict) -> None:
    api = _api()
    profile = api._read_profile_in_connection(connection, worker_id)
    before = _contribution(old) if old else (0, 0, 0)
    after = _contribution(new)
    updated = {
        field: int(profile.get(field) or 0) + after[index] - before[index]
        for index, field in enumerate(("rating", "success_requests", "fail_requests"))
    }
    if updated["success_requests"] < 0 or updated["fail_requests"] < 0:
        raise HTTPException(status_code=409, detail="Счетчики старой оценки требуют проверки; изменения не сохранены")
    api._write_profile_in_connection(connection, worker_id, {**profile, **updated})


def _begin(connection: Any) -> None:
    if _api()._is_sqlite_connection(connection):
        connection.execute("BEGIN IMMEDIATE")


def _owned_order(connection: Any, order_id: str, user: dict, profile: dict) -> dict:
    api = _api()
    order = api.read_order_in_connection(connection, order_id, for_update=True)
    if order is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if not api.logist_owns_order(order, user, profile=profile):
        raise HTTPException(status_code=403, detail="Оценку может изменить только ответственный логист")
    return order


def _revision_snapshot(review: dict) -> dict:
    return {key: deepcopy(review[key]) for key in (
        "result", "rating_delta", "reviewed_at", "reviewed_by", "reason",
        "revision", "request_id",
    ) if key in review}


def _save(connection: Any, order: dict, worker_id: str, review: dict,
          user: dict, event: str, details: dict) -> None:
    api = _api()
    order["worker_reviews"] = {**(order.get("worker_reviews") or {}), worker_id: review}
    # Keep order status, amounts, hours and its JSON updated_at unchanged.
    api.write_order_in_connection(connection, order)
    api.record_audit_event_in_connection(
        connection, event_type=event, outcome="success",
        actor_account_id=str(user["sub"]), actor_username=str(user.get("username") or ""),
        target_type="order", target_id=str(order.get("id") or order["external_order_id"]),
        details={"worker_id": worker_id, **details},
    )
    if not api._is_sqlite_connection(connection):
        connection.commit()


def submit_review(order_id: str, worker_id: str, result: str,
                  user: dict, *, reason: str = "") -> dict:
    api = _api()
    api.require_role(user, "logist")
    if result not in api.WORKER_RESULT_DELTAS:
        raise HTTPException(status_code=422, detail="Неизвестная оценка")
    profile = api.get_account_profile(user)
    with api.db_connection() as connection:
        _begin(connection)
        order = _owned_order(connection, order_id, user, profile)
        if worker_id not in [str(item) for item in order.get("assigned_worker_ids") or []]:
            raise HTTPException(status_code=403, detail="Исполнитель не назначен на заявку")
        existing = (order.get("worker_reviews") or {}).get(worker_id)
        if existing is not None:
            if existing.get("result") != result:
                raise HTTPException(status_code=409, detail="Оценка уже сохранена. Используйте исправление с причиной")
            return {"order": order, "review": existing, "already_recorded": True}
        if order.get("status") not in {"DONE_PENDING", "CONVERTED"}:
            raise HTTPException(status_code=409, detail="Оценка доступна после выполнения заявки; отмененные заявки не оцениваются")
        reason = _text(reason, required=result in {"good", "fail"})
        review = {
            "result": result, "rating_delta": api.WORKER_RESULT_DELTAS[result],
            "reviewed_at": _now(), "reviewed_by": str(user["sub"]),
            "reason": reason, "revision": 1, "appeals": [],
        }
        review["revisions"] = [_revision_snapshot(review)]
        _change_balance(connection, worker_id, {}, review)
        _save(connection, order, worker_id, review, user, "order_worker_reviewed",
              {"result": result, "rating_delta": review["rating_delta"], "reason": reason})
    return {"order": order, "review": review, "already_recorded": False}


def correct_review(order_id: str, worker_id: str, result: str, user: dict, *,
                   reason: str, expected_revision: int, request_id: str) -> dict:
    api = _api()
    api.require_role(user, "logist")
    if result not in {*api.WORKER_RESULT_DELTAS, "void"}:
        raise HTTPException(status_code=422, detail="Неизвестная оценка")
    reason = _text(reason, required=True)
    expected_revision = _expected_version(expected_revision)
    request_id = _request_id(request_id)
    profile = api.get_account_profile(user)
    with api.db_connection() as connection:
        _begin(connection)
        order = _owned_order(connection, order_id, user, profile)
        old = deepcopy((order.get("worker_reviews") or {}).get(worker_id))
        if not isinstance(old, dict):
            raise HTTPException(status_code=404, detail="Оценка не найдена")
        revisions = deepcopy(old.get("revisions") or [_revision_snapshot(old)])
        for item in revisions:
            if item.get("request_id") == request_id:
                if (item.get("result"), item.get("reason"), item.get("reviewed_by")) != (result, reason, str(user["sub"])):
                    raise HTTPException(status_code=409, detail="Идентификатор запроса уже использован")
                return {"order": order, "review": old, "already_recorded": True}
        if _version(old) != expected_revision:
            raise HTTPException(status_code=409, detail="Оценка уже изменилась. Обновите историю")
        if old.get("result") == result:
            raise HTTPException(status_code=409, detail="Выберите другую оценку или аннулирование")
        if len(revisions) >= 100:
            raise HTTPException(status_code=409, detail="Для этой оценки требуется отдельная проверка истории")
        new = {**old, "result": result, "rating_delta": api.WORKER_RESULT_DELTAS.get(result, 0),
               "reason": reason, "reviewed_at": _now(), "reviewed_by": str(user["sub"]),
               "revision": _version(old) + 1, "request_id": request_id}
        revisions.append(_revision_snapshot(new))
        new["revisions"] = revisions
        new["appeals"] = deepcopy(old.get("appeals") or [])
        for appeal in new["appeals"]:
            if appeal.get("status") == "open":
                appeal.update(status="resolved", decision="changed", resolved_at=new["reviewed_at"],
                              resolution=reason, resolved_by=str(user["sub"]))
        _change_balance(connection, worker_id, old, new)
        _save(connection, order, worker_id, new, user, "order_worker_review_corrected",
              {"previous_result": old.get("result"), "result": result,
               "rating_difference": _contribution(new)[0] - _contribution(old)[0],
               "reason": reason, "revision": new["revision"], "request_id": request_id})
    return {"order": order, "review": new, "already_recorded": False}


def appeal_review(order_id: str, user: dict, *, reason: str,
                  expected_revision: int, request_id: str) -> dict:
    api = _api()
    api.require_role(user, "worker")
    worker_id = str(user["sub"])
    reason = _text(reason, required=True)
    expected_revision = _expected_version(expected_revision)
    request_id = _request_id(request_id)
    with api.db_connection() as connection:
        _begin(connection)
        order = api.read_order_in_connection(connection, order_id, for_update=True)
        if order is None:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        review = deepcopy((order.get("worker_reviews") or {}).get(worker_id))
        if not isinstance(review, dict):
            raise HTTPException(status_code=403, detail="Нет собственной оценки по этой заявке")
        appeals = deepcopy(review.get("appeals") or [])
        for item in appeals:
            if item.get("request_id") == request_id:
                if item.get("reason") != reason or item.get("revision") != expected_revision:
                    raise HTTPException(status_code=409, detail="Идентификатор запроса уже использован")
                return {"order": order, "review": review, "already_recorded": True}
        if _version(review) != expected_revision:
            raise HTTPException(status_code=409, detail="Оценка изменилась. Обновите историю")
        if review.get("result") == "void":
            raise HTTPException(status_code=409, detail="Оценка уже аннулирована")
        if any(item.get("status") == "open" or item.get("revision") == expected_revision for item in appeals):
            raise HTTPException(status_code=409, detail="Обращение по этой версии уже зарегистрировано")
        if len(appeals) >= 50:
            raise HTTPException(status_code=409, detail="Для этой оценки требуется отдельная проверка обращений")
        appeals.append({"revision": expected_revision, "request_id": request_id, "reason": reason,
                        "created_at": _now(), "status": "open"})
        review["appeals"] = appeals
        _save(connection, order, worker_id, review, user, "order_worker_rating_appealed",
              {"revision": expected_revision, "reason": reason, "request_id": request_id})
    return {"order": order, "review": review, "already_recorded": False}


def resolve_appeal(order_id: str, worker_id: str, user: dict, *, reason: str,
                   expected_revision: int, request_id: str) -> dict:
    api = _api()
    api.require_role(user, "logist")
    reason = _text(reason, required=True)
    expected_revision = _expected_version(expected_revision)
    request_id = _request_id(request_id)
    profile = api.get_account_profile(user)
    with api.db_connection() as connection:
        _begin(connection)
        order = _owned_order(connection, order_id, user, profile)
        review = deepcopy((order.get("worker_reviews") or {}).get(worker_id))
        if not isinstance(review, dict):
            raise HTTPException(status_code=404, detail="Оценка не найдена")
        appeals = deepcopy(review.get("appeals") or [])
        for item in appeals:
            if item.get("resolution_request_id") == request_id:
                if item.get("resolution") != reason or item.get("resolved_by") != str(user["sub"]):
                    raise HTTPException(status_code=409, detail="Идентификатор запроса уже использован")
                return {"order": order, "review": review, "already_recorded": True}
        if _version(review) != expected_revision:
            raise HTTPException(status_code=409, detail="Оценка изменилась. Обновите историю")
        pending = [item for item in appeals if item.get("status") == "open"]
        if not pending:
            raise HTTPException(status_code=409, detail="Нет открытого обращения")
        pending[-1].update(status="resolved", decision="upheld", resolution=reason,
                           resolved_at=_now(), resolved_by=str(user["sub"]),
                           resolution_request_id=request_id)
        review["appeals"] = appeals
        _save(connection, order, worker_id, review, user, "order_worker_rating_appeal_resolved",
              {"reason": reason, "revision": expected_revision, "request_id": request_id})
    return {"order": order, "review": review, "already_recorded": False}


def visible_review(review: dict, *, staff: bool = False) -> dict:
    if staff:
        return deepcopy(review)
    allowed = ("result", "rating_delta", "reviewed_at", "reason", "revision")
    result = {key: deepcopy(review[key]) for key in allowed if key in review}
    result["revision"] = _version(review)
    result["revisions"] = [
        {key: deepcopy(item[key]) for key in allowed if key in item}
        for item in review.get("revisions") or [_revision_snapshot(review)]
    ]
    result["appeals"] = [
        {key: deepcopy(item[key]) for key in (
            "revision", "reason", "created_at", "status", "decision", "resolution", "resolved_at"
        ) if key in item}
        for item in review.get("appeals") or []
    ]
    return result


def _worker_orders(worker_id: str) -> list[dict]:
    api = _api()
    with api.db_connection() as connection:
        if api._is_sqlite_connection(connection):
            rows = connection.execute(
                f"""SELECT data FROM {api.TABLE_NAME}
                WHERE EXISTS (SELECT 1 FROM json_each(data, '$.worker_reviews') WHERE key = ?)
                   OR EXISTS (SELECT 1 FROM json_each(data, '$.assigned_worker_ids') WHERE value = ?)""",
                (worker_id, worker_id),
            ).fetchall()
        else:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""SELECT data FROM {api.TABLE_NAME}
                    WHERE data->'worker_reviews' ? %s
                       OR data->'assigned_worker_ids' @> %s::jsonb""",
                    (worker_id, json.dumps([worker_id])),
                )
                rows = cursor.fetchall()
    return [api.ensure_order_display_title(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
            for row in rows]


def summary(worker_id: str, *, profile: dict | None = None, orders: list[dict] | None = None) -> dict:
    api = _api()
    profile = profile if profile is not None else api.get_account_profile(api._worker_account(worker_id))
    orders = orders if orders is not None else _worker_orders(worker_id)
    reviews = [review for order in orders
               if isinstance(review := (order.get("worker_reviews") or {}).get(worker_id), dict)]
    counts = {key: sum(item.get("result") == key for item in reviews)
              for key in (*api.WORKER_RESULT_DELTAS, "void")}
    count = sum(counts[key] for key in api.WORKER_RESULT_DELTAS)
    positive = counts["success"] + counts["excellent"]
    recorded_points = sum(_contribution(item)[0] for item in reviews if item.get("result") in {*api.WORKER_RESULT_DELTAS, "void"})
    score = int(profile.get("rating") or 0)
    return {
        "rating": score, "review_count": count, "positive_count": positive,
        "positive_percent": round(100 * positive / count) if count else None,
        "concern_count": counts["good"], "unsuccessful_count": counts["fail"],
        "void_count": counts["void"],
        "has_legacy_balance": (
            score != recorded_points or
            int(profile.get("success_requests") or 0) != positive or
            int(profile.get("fail_requests") or 0) != counts["fail"]
        ),
    }


def history(worker_id: str, user: dict, *, offset: int = 0, limit: int = 20) -> dict:
    api = _api()
    role = user.get("role")
    if role != "logist" and not (role == "worker" and str(user["sub"]) == worker_id):
        raise HTTPException(status_code=403, detail="История доступна только рабочему и логисту")
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="Некорректная страница")
    profile = api.get_account_profile(api._worker_account(worker_id))
    actor_profile = api.get_account_profile(user) if role == "logist" else None
    orders = _worker_orders(worker_id)
    items = []
    for order in orders:
        manages = role == "logist" and api.logist_owns_order(order, user, profile=actor_profile)
        if role == "logist" and not manages:
            continue
        review = (order.get("worker_reviews") or {}).get(worker_id)
        if not isinstance(review, dict) and order.get("status") not in {"DONE_PENDING", "CONVERTED"}:
            continue
        items.append({
            "order_id": str(order.get("id") or order.get("external_order_id") or ""),
            "order_title": str(order.get("title") or "Заявка"),
            "order_status": order.get("status"),
            "can_manage": bool(manages),
            "can_review": bool(manages and not review and order.get("status") in {"DONE_PENDING", "CONVERTED"}),
            "review": visible_review(review, staff=bool(manages)) if isinstance(review, dict) else None,
            "date": str((review or {}).get("reviewed_at") or order.get("updated_at") or order.get("created_at") or ""),
        })
    items.sort(key=lambda item: (item["date"], item["order_id"]), reverse=True)
    page = items[offset:offset + limit]
    return {"summary": summary(worker_id, profile=profile, orders=orders),
            "history": page, "has_more": offset + len(page) < len(items),
            "next_offset": offset + len(page),
            "scope": "own_orders" if role == "logist" else "self"}


def register_routes(app) -> None:
    from fastapi import Header, Query, Request, Response

    @app.get("/app-api/me/rating")
    async def own_rating(response: Response, authorization: str | None = Header(default=None),
                         offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100)):
        api = _api()
        user = await api.authenticated_user(authorization)
        api.require_role(user, "worker")
        response.headers["Cache-Control"] = "no-store"
        return await api.asyncio.to_thread(history, str(user["sub"]), user, offset=offset, limit=limit)

    @app.get("/app-api/logist/workers/{worker_id}/rating")
    async def staff_rating(worker_id: str, response: Response,
                           authorization: str | None = Header(default=None),
                           offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100)):
        api = _api()
        user = await api.authenticated_user(authorization)
        api.require_role(user, "logist")
        response.headers["Cache-Control"] = "no-store"
        return await api.asyncio.to_thread(history, worker_id, user, offset=offset, limit=limit)

    async def mutate(operation, order_id, request, authorization, *, worker_argument=True):
        api = _api()
        user = await api.authenticated_user(authorization)
        api.require_role(user, "logist" if worker_argument else "worker")
        payload = await api.bounded_json_payload(request, max_bytes=4096)
        fields = {"reason", "expected_revision", "request_id"}
        if worker_argument:
            fields.add("worker_id")
        if operation is correct_review:
            fields.add("result")
        if set(payload) != fields:
            raise HTTPException(status_code=422, detail="Некорректные поля запроса")
        arguments = [order_id]
        try:
            if worker_argument:
                arguments.append(api.bounded_text(payload["worker_id"], "worker_id", max_length=120, required=True))
            if operation is correct_review:
                arguments.append(api.bounded_text(payload["result"], "result", max_length=30, required=True))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        arguments.append(user)
        saved = await api.asyncio.to_thread(
            operation, *arguments, reason=payload["reason"],
            expected_revision=payload["expected_revision"], request_id=payload["request_id"],
        )
        return {"success": True, "already_recorded": saved["already_recorded"],
                "order": api.order_for_user(saved["order"], user),
                "review": visible_review(saved["review"], staff=worker_argument)}

    @app.post("/app-api/me/order-rating-corrections/{order_id:path}")
    async def correction(order_id: str, request: Request, authorization: str | None = Header(default=None)):
        return await mutate(correct_review, order_id, request, authorization)

    @app.post("/app-api/me/order-rating-appeals/{order_id:path}")
    async def appeal(order_id: str, request: Request, authorization: str | None = Header(default=None)):
        return await mutate(appeal_review, order_id, request, authorization, worker_argument=False)

    @app.post("/app-api/me/order-rating-resolutions/{order_id:path}")
    async def resolution(order_id: str, request: Request, authorization: str | None = Header(default=None)):
        return await mutate(resolve_appeal, order_id, request, authorization)
