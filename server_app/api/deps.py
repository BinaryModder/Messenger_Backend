from typing import Optional


from database.session import LocalSession


def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()
