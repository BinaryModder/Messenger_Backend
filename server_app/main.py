from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from core.config import settings
from api.v1.api import api_router
from database.session import Base, engine
import models

app = FastAPI()

Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return RedirectResponse(url="/docs")


app.include_router(api_router)


if __name__ == "__main__":

    import uvicorn

    uvicorn.run("main:app", host=settings.API_HOST,
                port=settings.API_PORT, log_level=settings.LOG_LEVEL, reload=True)
