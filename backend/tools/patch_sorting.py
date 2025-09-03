import re, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP  = ROOT / "app"

def ensure_sorting_helper():
    """Создаём общий хелпер apply_sorting(model, query, sort_param) если его нет."""
    utils_dir = APP / "utils"
    utils_dir.mkdir(parents=True, exist_ok=True)
    f = utils_dir / "sorting.py"
    if f.exists():
        return False
    f.write_text("""\
from typing import Optional
from sqlalchemy.sql import text

def apply_sorting(query, model, sort_param: Optional[str]):
    \"\"\"Применяет мультисортировку вида 'field1,-field2'.
    Допускает имена колонок из атрибутов model. Неизвестные игнорирует.
    Пример: sort=-created_at,name
    \"\"\"
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
""", encoding="utf-8")
    return True

def patch_file(path: Path, model_hint_regex: str, route_hint_regex: str):
    """Патчим модуль: добавляем импорт хелпера и поддержку Query-параметра sort."""
    txt = path.read_text(encoding="utf-8")

    # 1) импорт
    if "from app.utils.sorting import apply_sorting" not in txt:
        # добавим рядом с другими импортами
        txt = re.sub(r"(^from .+?\n)+", lambda m: m.group(0) + "from app.utils.sorting import apply_sorting\n", txt, count=1, flags=re.M)

    # 2) убедимся, что из fastapi импортирован Query
    if "from fastapi import" in txt and " Query" not in txt:
        txt = re.sub(r"(from fastapi import [^\n]+)", r"\1, Query", txt, count=1)
    elif "from fastapi import" not in txt:
        txt = "from fastapi import Query\n" + txt

    # 3) найдём сигнатуру функции-обработчика по route_hint_regex
    #    и добавим параметр sort: str | None = Query(None, alias="sort")
    def add_sort_param(m):
        header = m.group(0)
        if "alias=\"sort\"" in header or "alias='sort'" in header:
            return header  # уже пропатчено
        # вставляем параметр перед закрывающей скобкой def(...):
        header = re.sub(r"\)\s*:", r", sort: str | None = Query(None, alias='sort')):", header)
        return header

    txt_new = re.sub(route_hint_regex, add_sort_param, txt, flags=re.M | re.S)
    changed = (txt_new != txt)
    txt = txt_new

    # 4) вставим вызов apply_sorting(..) перед .offset/.limit или перед .all()
    #    ориентируемся на присутствие model_hint_regex (имя ORM-модели)
    #    и шаблон query = ...query...
    # Попробуем заменить первую выборку:
    pattern_query = re.compile(r"(\n\s*query\s*=\s*.+?\n)(\s*(?:query\s*=\s*query\..+?\n)*)", re.S)
    if pattern_query.search(txt):
        def inject_apply(m):
            prefix = m.group(0)
            if "apply_sorting(" in prefix:
                return prefix  # уже было
            return prefix + "\n" + " " * 4 + f"query = apply_sorting(query, {model_hint_regex}, sort)\n"
        txt = pattern_query.sub(inject_apply, txt, count=1)
    else:
        # fallback: просто попробуем перед .all() вставить apply_sorting(...)
        txt = re.sub(r"(query\s*=\s*.+?\n)(\s*items\s*=\s*query\.all\(\))",
                     r"\1    query = apply_sorting(query, " + model_hint_regex + r", sort)\n\2",
                     txt, count=1, flags=re.S)

    path.write_text(txt, encoding="utf-8")
    return changed

def detect_and_patch():
    created_helper = ensure_sorting_helper()

    # Поиск модулей: рекомендации и csv
    candidates = list(APP.rglob("*.py"))

    # Грубые эвристики маршрутов и моделей
    patched = []

    # 1) Рекомендации: ищем маршрут /companies/{id}/recommendations/paged
    rec_files = [p for p in candidates if "recomm" in p.name.lower() or "recomm" in str(p)]
    if not rec_files:
        rec_files = candidates  # fallback: проверим все

    for f in rec_files:
        txt = f.read_text(encoding="utf-8")
        if re.search(r"recommendations/paged", txt):
            # Пытаемся угадать модель Recommendation
            model_name = "Recommendation"
            m = re.search(r"class\s+(\w*Recommendation\w*)\s*\(", txt)
            if m:
                model_name = m.group(1)
            changed = patch_file(f, model_name, route_hint_regex=r"@router\.(?:get|post)\(.+recommendations/paged.+\)\s*\ndef\s+\w+\s*\(.*?\)\s*:")
            if changed:
                patched.append(str(f))

    # 2) CSV-экспорт: ищем маршруты с export/csv
    csv_files = [p for p in candidates if "export" in p.name.lower() or "csv" in p.name.lower()] or candidates
    for f in csv_files:
        txt = f.read_text(encoding="utf-8")
        if re.search(r"(export|csv)", txt, re.I):
            # Пытаемся угадать модель Company/Recommendation
            model_name = "Company"
            if "Recommendation" in txt:
                model_name = "Recommendation"
            changed = patch_file(f, model_name, route_hint_regex=r"@router\.(?:get|post)\(.+(?:export|csv).+\)\s*\ndef\s+\w+\s*\(.*?\)\s*:")
            if changed:
                patched.append(str(f))

    print(json.dumps({
        "created_helper": created_helper,
        "patched_files": patched,
    }))

if __name__ == "__main__":
    detect_and_patch()
