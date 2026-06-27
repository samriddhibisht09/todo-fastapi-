from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
import bcrypt
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import Todo, User
from app.schemas import (
    Token,
    TokenData,
    TodoCreate,
    TodoRead,
    TodoUpdate,
    UserCreate,
    UserLogin,
    UserRead,
)

SECRET_KEY = "e9f5d4b0c8a04a86b1af7ebf6f4d2c7a"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

security = HTTPBearer()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(item) for item in err.get("loc", []))
        msg = err.get("msg", "Invalid input")
        errors.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(errors) or "Invalid request"},
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database_schema():
    Base.metadata.create_all(bind=engine)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(todos)"))
            columns = [row[1] for row in result]
            if "user_id" not in columns:
                conn.execute(text("ALTER TABLE todos ADD COLUMN user_id INTEGER"))
    except Exception:
        pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(username=email)
    except JWTError:
        raise credentials_exception
    user = get_user_by_email(db, token_data.username)
    if user is None:
        raise credentials_exception
    return user


ensure_database_schema()


@app.get("/", response_class=FileResponse)
def read_index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/home")
def home():
    return {"message": "Todo API Running with SQLite Database"}


@app.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, user_data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    password_bytes = user_data.password.encode("utf-8")
    if len(password_bytes) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be 72 bytes or less",
        )

    new_user = User(
        email=user_data.email,
        phone_number=user_data.phone_number,
        hashed_password=get_password_hash(user_data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/users", response_model=List[UserRead])
def get_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(User).all()


@app.get("/todos", response_model=List[TodoRead])
def get_todos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Todo).filter(Todo.user_id == current_user.id).all()


@app.post("/todos", response_model=TodoRead, status_code=status.HTTP_201_CREATED)
def add_todo(
    todo_data: TodoCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = validate_task(todo_data.task)

    existing_todo = (
        db.query(Todo)
        .filter(Todo.user_id == current_user.id)
        .filter(Todo.task.ilike(task))
        .first()
    )

    if existing_todo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task already exists")

    new_todo = Todo(task=task, completed=False, user_id=current_user.id)
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return new_todo


@app.get("/todos/stats")
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    todos = db.query(Todo).filter(Todo.user_id == current_user.id).all()

    total = len(todos)
    completed = sum(1 for todo in todos if todo.completed)
    pending = total - completed
    completed_tasks = [todo.task for todo in todos if todo.completed]
    pending_tasks = [todo.task for todo in todos if not todo.completed]
    completion_percentage = round((completed / total) * 100, 2) if total > 0 else 0

    return {
        "total_tasks": total,
        "completed_tasks_count": completed,
        "pending_tasks_count": pending,
        "completion_percentage": completion_percentage,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
    }


@app.get("/todos/{todo_id}", response_model=TodoRead)
def get_todo(
    todo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    todo = (
        db.query(Todo)
        .filter(Todo.id == todo_id)
        .filter(Todo.user_id == current_user.id)
        .first()
    )
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    return todo


@app.put("/todos/{todo_id}", response_model=TodoRead)
def update_todo(
    todo_id: int,
    todo_data: TodoUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    todo = (
        db.query(Todo)
        .filter(Todo.id == todo_id)
        .filter(Todo.user_id == current_user.id)
        .first()
    )
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")

    task = validate_task(todo_data.task)
    todo.task = task
    todo.completed = todo_data.completed

    db.commit()
    db.refresh(todo)
    return todo


@app.delete("/todos/{todo_id}")
def delete_todo(
    todo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    todo = (
        db.query(Todo)
        .filter(Todo.id == todo_id)
        .filter(Todo.user_id == current_user.id)
        .first()
    )
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    db.delete(todo)
    db.commit()
    return {"message": "Todo deleted"}


def validate_task(task: str):
    task = task.strip()
    if not task:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task cannot be empty")
    if task.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task cannot contain only numbers")
    if len(task) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task must be at least 3 characters")
    if len(task) > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task too long")
    if not any(char.isalpha() for char in task):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task must contain at least one letter")
    return task
