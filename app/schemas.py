from pydantic import BaseModel

class TodoCreate(BaseModel):
    task: str

class TodoUpdate(BaseModel):
    task: str
    completed: bool