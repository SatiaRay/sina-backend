from database.models import Base, engine

def run_migrations():
    """Create all database tables."""
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    run_migrations() 