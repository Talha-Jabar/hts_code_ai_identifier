from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore

from api.routes import fetch, preprocess, embeddings, classify, candidates, duty

app = FastAPI(title="HTS Classification API", version="1.0.0")

# CORS (adjust origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fetch.router, prefix="/fetch", tags=["Fetch"])
app.include_router(preprocess.router, prefix="/preprocess", tags=["Preprocess"])
app.include_router(embeddings.router, prefix="/embeddings", tags=["Embeddings"])
app.include_router(classify.router, prefix="/classify", tags=["Classification"])
app.include_router(candidates.router, prefix="/candidates", tags=["Candidates"])
app.include_router(duty.router, prefix="/duty", tags=["Duty"])

@app.get("/")
def root():
    return {"message": "HTS Classification API running"}
