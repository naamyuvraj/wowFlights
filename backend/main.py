from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.concierge import router as concierge_router

app = FastAPI(title="WoWFlights Core AI Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(concierge_router)

@app.get("/")
def health_check():
    return {"status": "System Online", "version": "1.0.0"}