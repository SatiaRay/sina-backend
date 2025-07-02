
from sqlalchemy.orm import Session, Query
from provider.service_container import container
from .repository_base import RepositoryBase
from database.models import BaseModel
from typing import List, Optional, Type, TypeVar, Generic

T = TypeVar('T', bound=BaseModel)

class CustomSession(Session):
    def __init__(self, db_session: Session):
        """
        This constructor initializes a custom session by wrapping the base session and applying tenancy conditions.
        """
        super().__init__(bind=db_session.bind, autoflush=db_session.autoflush)

    def apply_tenancy_filter(self, query: Query, model: T) -> Query:
        """
        Apply the tenancy filter to the query if the workspace_id is set.
        """
        user = container.make('auth_user')       
        
        if not user.current_workspace_id:
            raise Exception("User current workspace is None")
            
        print(user.email)
        print(f"CURRENT WORKSPACE ID IS {user.current_workspace_id}")
        return query.filter(model.workspace_id == user.current_workspace_id )
        
    def query(self, *args, **kwargs):
        """
        Override the query method to automatically apply the tenancy filter for any query.
        """
        model = args[0]
        query = super().query(*args, **kwargs)
        if model:
            query = self.apply_tenancy_filter(query, model)
        return query
    
    
class TenancyRepository(RepositoryBase):
    def __init__(self, db_session: Session, model_class):
        # Wrap the base session with the custom session that applies tenancy filters
        self.model_class = model_class
        self.db = CustomSession(db_session=db_session)
        super().__init__(self.db, model_class) 
        
    def create(self, data: dict) -> T:
        if 'workspace_id' not in data:
            data['workspace_id'] = container.make('auth_user').current_workspace_id
        return super().create(data)