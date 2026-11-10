from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import chat_message as service


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def test_messages_are_returned_in_chronological_order(session):
    user = await make_user(session)
    await service.add_exchange(session, user.id, "uno", "respuesta uno")
    await service.add_exchange(session, user.id, "dos", "respuesta dos")
    messages = await service.get_recent_messages(session, user.id)
    assert [m.content for m in messages] == ["uno", "respuesta uno", "dos", "respuesta dos"]
    assert [m.role for m in messages] == ["user", "assistant", "user", "assistant"]


async def test_limit_keeps_latest_and_starts_with_user_message(session):
    user = await make_user(session)
    await service.add_exchange(session, user.id, "uno", "respuesta uno")
    await service.add_exchange(session, user.id, "dos", "respuesta dos")
    messages = await service.get_recent_messages(session, user.id, limit=3)
    assert [m.content for m in messages] == ["dos", "respuesta dos"]


async def test_messages_are_isolated_by_user(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    await service.add_exchange(session, ana.id, "hola", "hola ana")
    assert await service.get_recent_messages(session, beto.id) == []
