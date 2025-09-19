# ---------------------------
# File: app/main.py
# ---------------------------
from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from app.api.classify_router import router as classify_router
from app.api.classify_router import get_query_service
from app.api.duty_router import router_duty
from pathlib import Path
from chains.hts_chain import HTSOrchestrator

app = FastAPI(title="HTS Intelligent Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(classify_router)
app.include_router(router_duty)


@app.post("/api/pipeline/run")
def run_full_pipeline():
    """Run the same pipeline you used in Streamlit: fetch -> preprocess -> embed.
    This runs synchronously and may take time. In production you may want to offload
    to a worker or return a job id and run async; however your original Streamlit
    run was interactive so this keeps parity.
    """
    base = Path.cwd()
    orch = HTSOrchestrator(base)
    res = orch.run_full_pipeline()
    return {"raw": str(res['raw']), "processed": str(res['processed']), "points_indexed": res['points_indexed']}


@app.on_event("startup")
def startup_event():
    # Ensure QueryService is created if CSV present (warm start)
    try:
        get_query_service()
    except Exception:
        # Processed CSV may not be present yet; pipeline must be run
        pass