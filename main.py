from fastapi import FastAPI

app = FastAPI()

todos = []

@app.get("/")
def home():
    return {"message": "Todo API Running"}

@app.get("/todos")
def get_todos():
    return todos

@app.post("/todos")
def add_todo(task: str):
    todos.append(task)
    return {"message": "Todo added", "todos": todos}
