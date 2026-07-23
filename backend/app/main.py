import asyncio
import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .api.routes import router
from .auth.routes import admin_router, auth_router
from .auth.security import hash_password
from .config import APP_NAME
from .database import SessionLocal, init_db
from .models import User
from .services.runtime import load_custom_instruments
from .services.scheduler import run_forever
from .services.telegram_bot import poll_forever

DEFAULT_ADMIN = ("admin", "admin12345")  # смените пароль после первого входа


def _seed_admin() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(User).limit(1)) is None:
            username, password = DEFAULT_ADMIN
            db.add(User(username=username,
                        password_hash=hash_password(password), role="admin"))
            db.commit()
            print(f"[init] создан администратор: {username} / {password} — смените пароль")
    finally:
        db.close()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_admin()
    load_custom_instruments()
    tasks = [asyncio.create_task(run_forever()),
             asyncio.create_task(poll_forever())]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title=f"{APP_NAME} API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(router)
