import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Cookie, Response, BackgroundTasks
from sqlalchemy.orm  import Session

from backend.db.database import get_db, SessionLocal
from backend.models.job import StoryJob
from backend.models.story import Story, StoryNode
from backend.schemas.story import (
    CompleteStoryResponse, CompleteStoryNodeResponse, CreateStoryRequest
)
from backend.schemas.job import StoryJobResponse

router = APIRouter(
    prefix="/stories",
    tags=["stories"]
)

def get_session_id(session_id: Optional[str] = Cookie(None)):
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id
    

@router.post("/create", response_model=StoryJobResponse)
def create_story(
    request: CreateStoryRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_db)
):
    response.set_cookie(key="session_id", value=session_id, httponly=True)

    job_id = str(uuid.uuid4())

    job = StoryJob(
        session_id=session_id,
        job_id=job_id,
        theme=request.theme,
        status="pending",
    )

    db.add(job)
    db.commit()

    background_tasks.add_task(generate_story_task, job_id=job_id, theme=request.theme, session_id=session_id)

    return job

def generate_story_task(job_id: str, theme: str, session_id: str):
    db = SessionLocal()

    try:
        job = db.query(StoryJob).filter(StoryJob.job_id == job.id).first()

        if not job:
            return
        
        try:
            job.status = "processing"
            db.commit()

            story = {}

            job.story_id = 1
            job.status = "completed"
            job.completed_at = datetime.now()
            db.commit()
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            db.commit()
    finally:
        db.close()


@router.get("/{story_id}", response_model=CompleteStoryResponse)
def get_complete_story(story_id: int, db: Session = Depends(get_db)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    root_node = db.query(StoryNode).filter(StoryNode.id == story.root_node_id).first()
    if not root_node:
        raise HTTPException(status_code=404, detail="Root story node not found")

    return story

def build_complete_story_tree(node: StoryNode, db: Session) -> CompleteStoryNodeResponse: