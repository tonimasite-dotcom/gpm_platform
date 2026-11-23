"""Small authenticated endpoints; CRM secrets stay server-side."""
import asyncio
from fastapi import Header, Request, Response

from app import crew_storage as s
from app import crew_flow as flow
from app import crew_confirmation as confirmation


def public_base(request):
    return (s.api().get_setting("GPM_APP_PUBLIC_API_URL", "https://app-api.gpmbot.ru")
            if s.api().is_production_environment() else str(request.base_url).rstrip("/"))


async def user_for(authorization, response):
    response.headers["Cache-Control"] = "no-store"
    return await s.api().authenticated_user(authorization)


def receipt(session_id, user):
    with s.transaction() as connection:
        session = s.one(connection, f"SELECT * FROM {s.SESSIONS} WHERE session_id=?", (session_id,))
        if not session:
            from fastapi import HTTPException
            raise HTTPException(404, "Сбор не найден")
        order = s.load_order(connection, session["order_id"], user)
        if user.get("role") == "worker" and s.actor(user) != session["leader_account_id"]:
            from fastapi import HTTPException
            raise HTTPException(403, "Нет доступа к этому сбору")
        return flow.session_view(connection, session, user)


def register(app):
    @app.get("/app-api/me/crew-attendance/{order_id:path}/state")
    async def crew_state(order_id: str, response: Response, authorization: str | None = Header(default=None)):
        user = await user_for(authorization, response)
        return await asyncio.to_thread(flow.state, order_id, user)

    @app.post("/app-api/me/crew-attendance/{order_id:path}/leader")
    async def crew_leader(order_id: str, request: Request, response: Response,
                          authorization: str | None = Header(default=None)):
        user = await user_for(authorization, response)
        body = await s.api().bounded_json_payload(request, max_bytes=2048)
        return await asyncio.to_thread(flow.set_leader, order_id, user, str(body.get("worker_account_id") or ""))

    @app.post("/app-api/me/crew-attendance/{order_id:path}/presence")
    async def crew_presence(order_id: str, request: Request, response: Response,
                            authorization: str | None = Header(default=None)):
        user = await user_for(authorization, response)
        body = await s.api().bounded_json_payload(request, max_bytes=8192)
        return await asyncio.to_thread(flow.presence, order_id, user, body.get("location"),
                                       body.get("action"), public_base(request))

    @app.post("/app-api/me/crew-attendance/{order_id:path}/sessions")
    async def crew_start(order_id: str, request: Request, response: Response,
                         authorization: str | None = Header(default=None)):
        user = await user_for(authorization, response)
        body = await s.api().bounded_json_payload(request, max_bytes=8192)
        return await asyncio.to_thread(flow.start, order_id, user, body.get("action"), body.get("location"))

    @app.get("/app-api/me/crew-sessions/{session_id}")
    async def crew_receipt(session_id: str, response: Response, authorization: str | None = Header(default=None)):
        user = await user_for(authorization, response)
        return await asyncio.to_thread(receipt, session_id, user)

    @app.post("/app-api/me/crew-sessions/{session_id}/scan")
    async def crew_scan(session_id: str, request: Request, response: Response,
                        authorization: str | None = Header(default=None)):
        user = await user_for(authorization, response)
        body = await s.api().bounded_json_payload(request, max_bytes=8192)
        return await asyncio.to_thread(flow.scan, session_id, user, str(body.get("token") or ""), body.get("location"))

    @app.post("/app-api/me/crew-sessions/{session_id}/freeze")
    async def crew_freeze(session_id: str, request: Request, response: Response,
                          authorization: str | None = Header(default=None)):
        user = await user_for(authorization, response)
        return await asyncio.to_thread(flow.freeze, session_id, user, public_base(request))

    @app.post("/app-api/me/crew-sessions/{session_id}/cancel")
    async def crew_cancel(session_id: str, response: Response, authorization: str | None = Header(default=None)):
        user = await user_for(authorization, response)
        return await asyncio.to_thread(flow.cancel, session_id, user)

    @app.post("/app-api/me/crew-reviews/{evidence_id}")
    async def crew_review(evidence_id: str, request: Request, response: Response,
                          authorization: str | None = Header(default=None)):
        user = await user_for(authorization, response)
        body = await s.api().bounded_json_payload(request, max_bytes=8192)
        return await asyncio.to_thread(confirmation.review, evidence_id, user,
                                       str(body.get("decision") or ""), body.get("reason"))

    @app.post("/app-api/integration/crew-attendance/{order_id:path}")
    async def crm_crew(order_id: str, request: Request, response: Response,
                       x_gpm_app_token: str | None = Header(default=None)):
        s.api().check_token(x_gpm_app_token)
        response.headers["Cache-Control"] = "no-store"
        body = await s.api().bounded_json_payload(request, max_bytes=32768)
        operation = body.get("operation")
        functions = {"export": confirmation.export, "link": confirmation.link_worker,
                     "roster": confirmation.sync_roster, "review": confirmation.crm_review}
        if operation not in functions:
            from fastapi import HTTPException
            raise HTTPException(422, "Неизвестное действие табеля")
        return await asyncio.to_thread(functions[operation], order_id, body)
