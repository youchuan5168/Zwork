from app.core.errors import BusinessError

STAGES = frozenset(
    {
        "not_started",
        "applied",
        "screening",
        "written_test",
        "interview",
        "offer",
        "rejected",
        "withdrawn",
    }
)


def require(entity, detail):
    if entity is None:
        raise BusinessError(detail, 404)
    return entity


def apply_fields(entity, data):
    for key, value in data.items():
        setattr(entity, key, value)
