from fastapi import FastAPI
from app.api import companies, analysis

app = FastAPI(title="BizLeo API")

app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(analysis.router,  prefix="/companies", tags=["analysis"])

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
