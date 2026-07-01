from fastapi import FastAPI

app = FastAPI(title="입고자재 송장관리 API")


@app.get("/health")
def health():
    return {"status": "ok"}
