from sqlalchemy.orm import Session, Query
from typing import List, Optional, Type, TypeVar, Generic
from datetime import datetime

from provider.service_container import container
from database.models import BaseModel

T = TypeVar('T', bound=BaseModel)

class RepositoryBase(Generic[T]):
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