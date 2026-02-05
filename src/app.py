from fastapi import FastAPI

from plagiarism.router import router as router_plagiarism

from exceptions.error_handler import add_exception_handler
from startup.create_exchange import create_queues_and_exchanges



app = FastAPI(title="Plagiarism Detection API")


app.include_router(router_plagiarism)

add_exception_handler(app)


@app.on_event("startup")
async def on_startup():
    await create_queues_and_exchanges()


@app.get("/")
async def root():
    return {"message": "Plagiarism Detection API"}
