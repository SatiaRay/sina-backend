from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database.repository import InstructionRepository
from database.models import Instruction
from database.models import get_db
from pydantic import BaseModel, Field, validator
from datetime import datetime

router = APIRouter()

class InstructionBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=1)
    status: bool = True

    @validator('label', 'text')
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()

class InstructionCreate(InstructionBase):
    pass

class InstructionUpdate(InstructionBase):
    pass

class InstructionResponse(InstructionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

@router.post("/instructions/", response_model=InstructionResponse)
def create_instruction(instruction: InstructionCreate, db: Session = Depends(get_db)):
    repo = InstructionRepository(db)
    return repo.create(instruction.dict())

@router.get("/instructions/", response_model=List[InstructionResponse])
def get_instructions(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    repo = InstructionRepository(db)
    if active_only:
        return repo.get_active_instructions()
    return repo.get_all()

@router.get("/instructions/{instruction_id}", response_model=InstructionResponse)
def get_instruction(instruction_id: int, db: Session = Depends(get_db)):
    repo = InstructionRepository(db)
    instruction = repo.get(instruction_id)
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    return instruction

@router.put("/instructions/{instruction_id}", response_model=InstructionResponse)
def update_instruction(
    instruction_id: int,
    instruction: InstructionUpdate,
    db: Session = Depends(get_db)
):
    repo = InstructionRepository(db)
    updated_instruction = repo.update(instruction_id, instruction.dict())
    if not updated_instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    return updated_instruction

@router.delete("/instructions/{instruction_id}")
def delete_instruction(instruction_id: int, db: Session = Depends(get_db)):
    repo = InstructionRepository(db)
    if not repo.delete(instruction_id):
        raise HTTPException(status_code=404, detail="Instruction not found")
    return {"message": "Instruction deleted successfully"}

@router.patch("/instructions/{instruction_id}/enable", response_model=InstructionResponse)
def enable_instruction(instruction_id: int, db: Session = Depends(get_db)):
    repo = InstructionRepository(db)
    instruction = repo.enable_instruction(instruction_id)
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    return instruction

@router.patch("/instructions/{instruction_id}/disable", response_model=InstructionResponse)
def disable_instruction(instruction_id: int, db: Session = Depends(get_db)):
    repo = InstructionRepository(db)
    instruction = repo.disable_instruction(instruction_id)
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    return instruction 