from sqlalchemy.orm import Session
from typing import List, Optional, Type, TypeVar, Generic
from datetime import datetime
from .models import BaseModel, Chat, ChatHistory, Document, Wizard, CrawledDomain, CrawlJobs, Instruction
from sqlalchemy.types import String
from sqlalchemy import text

T = TypeVar('T', bound=BaseModel)

class Repository(Generic[T]):
    def __init__(self, db: Session, model_class: Type[T]):
        self.db = db
        self.model_class = model_class

    def get_all(self) -> List[T]:
        return self.db.query(self.model_class).all()

    def get(self, id: int) -> Optional[T]:
        return self.db.query(self.model_class).filter(self.model_class.id == id).first()

    def create(self, data: dict) -> T:
        instance = self.model_class(**data)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def update(self, id: int, data: dict) -> Optional[T]:
        instance = self.get(id)
        if instance:
            for key, value in data.items():
                setattr(instance, key, value)
            self.db.commit()
            self.db.refresh(instance)
        return instance

    def delete(self, id: int) -> bool:
        instance = self.get(id)
        if instance:
            self.db.delete(instance)
            self.db.commit()
            return True
        return False

class WizardRepository(Repository[Wizard]):
    def __init__(self, db: Session):
        super().__init__(db, Wizard)

    def get_all(self, enable_only: bool = False) -> List[Wizard]:
        query = self.db.query(Wizard)
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        return query.all()

    def get(self, id: int, enable_only: bool = False) -> Optional[T]:
        query = self.db.query(self.model_class).filter(self.model_class.id == id)
        
        if enable_only:
            query = query.filter(self.model_class.enabled == True)
            
        wizard = query.first()

        if wizard:
            children_query = self.db.query(self.model_class).filter(self.model_class.parent_id == wizard.id)
            if enable_only:
                children_query = children_query.filter(self.model_class.enabled == True)
            wizard.children = children_query.all()
        
        return wizard

    def get_by_parent(self, parent_id: Optional[int], enable_only: bool = True) -> List[Wizard]:
        query = self.db.query(Wizard).filter(Wizard.parent_id == parent_id)
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        return query.all()

    def get_with_children(self, id: int, enable_only: bool = True) -> Optional[Wizard]:
        query = self.db.query(Wizard).filter(Wizard.id == id)
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        return query.first()

    def get_root_wizards(self, enable_only: bool = True) -> List[Wizard]:
        query = self.db.query(Wizard).filter(Wizard.parent_id.is_(None))
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        return query.all()

    def get_wizard_hierarchy(self, id: int, enable_only: bool = True) -> List[Wizard]:
        """Get a wizard and all its descendants"""
        wizard = self.get_with_children(id, enable_only)
        if not wizard:
            return []
        
        result = [wizard]
        children = self.get_by_parent(id, enable_only)
        for child in children:
            result.extend(self.get_wizard_hierarchy(child.id, enable_only))
        return result

    def enable_wizard(self, id: int) -> Optional[Wizard]:
        return self.update(id, {"enabled": True})

    def disable_wizard(self, id: int) -> Optional[Wizard]:
        return self.update(id, {"enabled": False})

    def get_enabled_wizards(self) -> List[Wizard]:
        return self.db.query(Wizard).filter(Wizard.enabled == True).all()

    def get_disabled_wizards(self) -> List[Wizard]:
        return self.db.query(Wizard).filter(Wizard.enabled == False).all()

class ChatRepository(Repository[Chat]):
    def __init__(self, db: Session):
        super().__init__(db, Chat)

    def get_with_messages(self, id: int) -> Optional[Chat]:
        return self.db.query(Chat).filter(Chat.session_id == id).first()

    def get_all_with_messages(self) -> List[Chat]:
        return self.db.query(Chat).all()
    
class ChatHistoryRepository(Repository[ChatHistory]):
    def __init__(self, db: Session):
        super().__init__(db, ChatHistory)

    def get_chat_history_by_chat_id(self, chat_id: int, limit:int = 20) -> List[ChatHistory]:
        """
        Retrieves all chat history messages associated with a specific chat.
        """
        return self.db.query(ChatHistory).filter(ChatHistory.chat_id == chat_id).limit(limit=limit).all()

    def get_with_chat_history(self, id: int) -> Optional[Chat]:
        """
        Retrieves a Chat and its associated ChatHistory messages.
        """
        return self.db.query(Chat).filter(Chat.id == id).join(Chat.chat_history).first()

class CrawledDomainRepository(Repository[CrawledDomain]):
    def __init__(self, db: Session):
        super().__init__(db, CrawledDomain)

    def get_by_domain(self, domain: str) -> Optional[CrawledDomain]:
        return self.db.query(CrawledDomain).filter(CrawledDomain.domain == domain).first()

    def get_or_create(self, domain: str) -> CrawledDomain:
        existing = self.get_by_domain(domain)
        if existing:
            return existing
        return self.create({"domain": domain})

class DocumentRepository(Repository[Document]):
    def __init__(self, db: Session):
        super().__init__(db, Document)

    def get_by_uri(self, uri: str) -> List[Document]:
        return self.db.query(Document).filter(Document.uri == uri).all()

    def get_by_domain(self, domain_id: int) -> List[Document]:
        return self.db.query(Document).filter(Document.domain_id == domain_id).all()

    def search_by_title(self, query: str) -> List[Document]:
        return self.db.query(Document).filter(Document.title.ilike(f"%{query}%")).all()

class CrawlJobsRepository(Repository[CrawlJobs]):
    def __init__(self, db: Session):
        super().__init__(db, CrawlJobs)

    def get_by_job_id(self, job_id: str) -> Optional[CrawlJobs]:
        """Get a crawl job by its job_id"""
        return self.db.query(CrawlJobs).filter(CrawlJobs.job_id == job_id).first()

    def get_active_jobs(self) -> List[CrawlJobs]:
        """Get all active crawl jobs (jobs without end_at set)"""
        return self.db.query(CrawlJobs).filter(CrawlJobs.end_at.is_(None)).all()

    def get_completed_jobs(self) -> List[CrawlJobs]:
        """Get all completed crawl jobs"""
        return self.db.query(CrawlJobs).filter(CrawlJobs.end_at.isnot(None)).all()

    def update_job_status(self, job_id: str, status: dict) -> Optional[CrawlJobs]:
        """Update the status of a crawl job"""
        job = self.get_by_job_id(job_id)
        if job:
            current_status = job.status or {}
            current_status.update(status)
            return self.update(job.id, {"status": current_status})
        return None

    def complete_job(self, job_id: str, status: dict = None) -> Optional[CrawlJobs]:
        """Mark a job as completed and update its status"""
        job = self.get_by_job_id(job_id)
        if job:
            update_data = {"end_at": datetime.utcnow()}
            if status:
                current_status = job.status or {}
                current_status.update(status)
                update_data["status"] = current_status
            return self.update(job.id, update_data)
        return None

    def add_log(self, job_id: str, log_message: str) -> Optional[CrawlJobs]:
        """Add a log message to the job's logs"""
        job = self.get_by_job_id(job_id)
        if job:
            current_logs = job.logs or ""
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            new_log = f"[{timestamp}] {log_message}\n"
            updated_logs = current_logs + new_log
            return self.update(job.id, {"logs": updated_logs})
        return None

    def get_jobs_by_domain(self, domain: str) -> List[CrawlJobs]:
        """Get all crawl jobs for a specific domain"""
        return self.db.query(CrawlJobs).filter(CrawlJobs.init_url.like(f"%{domain}%")).all()

    def get_recent_jobs(self, limit: int = 10) -> List[CrawlJobs]:
        """Get the most recent crawl jobs"""
        return self.db.query(CrawlJobs).order_by(CrawlJobs.started_at.desc()).limit(limit).all()

class InstructionRepository(Repository[Instruction]):
    def __init__(self, db: Session):
        super().__init__(db, Instruction)

    def get_all_paginated(self, page: int = 1, size: int = 10) -> tuple[List[Instruction], int]:
        """Get paginated instructions with non-empty label and text"""
        query = self.db.query(Instruction).filter(
            Instruction.label != '',
            Instruction.text != ''
        )
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def get_active_instructions_paginated(self, page: int = 1, size: int = 10) -> tuple[List[Instruction], int]:
        """Get paginated active instructions with non-empty label and text"""
        query = self.db.query(Instruction).filter(
            Instruction.status == True,
            Instruction.label != '',
            Instruction.text != ''
        )
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def get_inactive_instructions_paginated(self, page: int = 1, size: int = 10) -> tuple[List[Instruction], int]:
        """Get paginated inactive instructions with non-empty label and text"""
        query = self.db.query(Instruction).filter(
            Instruction.status == False,
            Instruction.label != '',
            Instruction.text != ''
        )
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def get_all(self) -> List[Instruction]:
        """Get all instructions with non-empty label and text"""
        return self.db.query(Instruction).filter(
            Instruction.label != '',
            Instruction.text != ''
        ).all()

    def get_active_instructions(self) -> List[Instruction]:
        """Get all active instructions with non-empty label and text"""
        return self.db.query(Instruction).filter(
            Instruction.status == True,
            Instruction.label != '',
            Instruction.text != ''
        ).all()

    def get_inactive_instructions(self) -> List[Instruction]:
        """Get all inactive instructions with non-empty label and text"""
        return self.db.query(Instruction).filter(
            Instruction.status == False,
            Instruction.label != '',
            Instruction.text != ''
        ).all()

    def get_by_label(self, label: str) -> Optional[Instruction]:
        """Get an instruction by its label"""
        return self.db.query(Instruction).filter(
            Instruction.label == label,
            Instruction.label != '',
            Instruction.text != ''
        ).first()

    def enable_instruction(self, id: int) -> Optional[Instruction]:
        """Enable an instruction"""
        return self.update(id, {"status": True})

    def disable_instruction(self, id: int) -> Optional[Instruction]:
        """Disable an instruction"""
        return self.update(id, {"status": False}) 