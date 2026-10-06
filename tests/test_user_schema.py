from app.schemas.user import UserCreate, UserRole


def test_self_registration_never_grants_privileged_roles():
    payload = UserCreate(email="a@b.fr", password="Passw0rdX1", role=UserRole.ADMIN)
    assert payload.as_self_registration().role == UserRole.ANALYST
