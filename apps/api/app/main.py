from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import init_db
from app.routes import billing, board, frameworks, models, objectives, reports, runs, tools


app = FastAPI(title="BioAutoScientist API", version="0.1.0")
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "bio-auto-scientist-api"}


app.include_router(objectives.router)
app.include_router(runs.router)
app.include_router(tools.router)
app.include_router(board.router)
app.include_router(reports.router)
app.include_router(billing.router)
app.include_router(models.router)
app.include_router(frameworks.router)
