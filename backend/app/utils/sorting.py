from typing import Optional
from sqlalchemy.sql import text

def apply_sorting(query, model, sort_param: Optional[str]):
    """Применяет мультисортировку вида 'field1,-field2'.
    Допускает имена колонок из атрибутов model. Неизвестные игнорирует.
    Пример: sort=-created_at,name
    """
    if not sort_param:
        return query
    fields = [s.strip() for s in sort_param.split(',') if s.strip()]
    order_clauses = []
    for fld in fields:
        direction = "asc"
        name = fld
        if fld.startswith('-'):
            direction = "desc"
            name = fld[1:]
        if hasattr(model, name):
            col = getattr(model, name)
            order_clauses.append(getattr(col, direction)())
    if order_clauses:
        return query.order_by(*order_clauses)
    return query
