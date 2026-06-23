from fastapi import FastAPI

app = FastAPI()

todos = []
next_id = 1



@app.get("/")
def home():
    return {"message": "Todo API Running"}


@app.get("/todos")
def get_todos():
    return todos


@app.post("/todos")
def add_todo(task: str):

    global next_id

    task = task.strip()

    if not task:
        return {"error": "Task cannot be empty"}

    if task.isdigit():
        return {"error": "Task cannot contain only numbers"}

    if len(task) < 3:
        return {"error": "Task must be at least 3 characters"}

    if len(task) > 100:
        return {"error": "Task too long"}

    if not any(char.isalpha() for char in task):
        return {"error": "Task must contain at least one letter"}

    for todo in todos:
        if todo["task"].lower() == task.lower():
            return {"error": "Task already exists"}

    new_todo = {
        "id": next_id,
        "task": task,
        "completed": False
    }

    todos.append(new_todo)

    next_id += 1

    return {
        "message": "Todo added",
        "todo": new_todo
    }
@app.get("/todos/stats")
def get_stats():

    total = len(todos)

    completed = 0
    pending = 0

    completed_tasks = []
    pending_tasks = []

    for todo in todos:

        if todo["completed"]:
            completed += 1
            completed_tasks.append(todo["task"])
        else:
            pending += 1
            pending_tasks.append(todo["task"])

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
def get_todo(todo_id: int):

    for todo in todos:
        if todo["id"] == todo_id:
            return todo

    return {"error": "Todo not found"}

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):


    for todo in todos:
        if todo["id"] == todo_id:
            todos.remove(todo)
            return {"message": "Todo deleted"}

    return {"error": "Todo not found"}
@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, task: str, completed: bool):

    task = task.strip()

    if not task:
        return {"error": "Task cannot be empty"}

    if task.isdigit():
        return {"error": "Task cannot contain only numbers"}

    if len(task) < 3:
        return {"error": "Task must be at least 3 characters"}

    if len(task) > 100:
        return {"error": "Task too long"}

    for todo in todos:

        if todo["id"] == todo_id:

            todo["task"] = task
            todo["completed"] = completed

            return {
                "message": "Todo updated",
                "todo": todo
            }

    return {"error": "Todo not found"}
#thank you 
#this is my code 
