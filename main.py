from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import engine, SessionLocal
from app.models import Base, Todo
from app.schemas import TodoCreate, TodoUpdate

app = FastAPI()

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def validate_task(task: str):
    task = task.strip()

    if not task:
        raise HTTPException(status_code=400, detail="Task cannot be empty")

    if task.isdigit():
        raise HTTPException(status_code=400, detail="Task cannot contain only numbers")

    if len(task) < 3:
        raise HTTPException(status_code=400, detail="Task must be at least 3 characters")

    if len(task) > 100:
        raise HTTPException(status_code=400, detail="Task too long")

    if not any(char.isalpha() for char in task):
        raise HTTPException(status_code=400, detail="Task must contain at least one letter")

    return task


@app.get("/home")
def home():
    return {"message": "Todo API Running with SQLite Database"}


@app.get("/todos")
def get_todos(db: Session = Depends(get_db)):
    todos = db.query(Todo).all()
    return todos


@app.post("/todos")
def add_todo(todo_data: TodoCreate, db: Session = Depends(get_db)):
    task = validate_task(todo_data.task)

    existing_todo = db.query(Todo).filter(Todo.task.ilike(task)).first()

    if existing_todo:
        raise HTTPException(status_code=400, detail="Task already exists")

    new_todo = Todo(task=task, completed=False)

    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)

    return {
        "message": "Todo added",
        "todo": new_todo
    }


@app.get("/todos/stats")
def get_stats(db: Session = Depends(get_db)):
    todos = db.query(Todo).all()

    total = len(todos)
    completed = 0
    pending = 0
    completed_tasks = []
    pending_tasks = []

    for todo in todos:
        if todo.completed:
            completed += 1
            completed_tasks.append(todo.task)
        else:
            pending += 1
            pending_tasks.append(todo.task)

    completion_percentage = 0

    if total > 0:
        completion_percentage = (completed / total) * 100

    return {
        "total_tasks": total,
        "completed_tasks_count": completed,
        "pending_tasks_count": pending,
        "completion_percentage": round(completion_percentage, 2),
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks
    }


@app.get("/todos/{todo_id}")
def get_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(Todo).filter(Todo.id == todo_id).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    return todo


@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, todo_data: TodoUpdate, db: Session = Depends(get_db)):
    task = validate_task(todo_data.task)

    todo = db.query(Todo).filter(Todo.id == todo_id).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    todo.task = task
    todo.completed = todo_data.completed

    db.commit()
    db.refresh(todo)

    return {
        "message": "Todo updated",
        "todo": todo
    }


@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(Todo).filter(Todo.id == todo_id).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    db.delete(todo)
    db.commit()

    return {"message": "Todo deleted"}
