"""Composable SQLite boundary: only the creator commits the outer transaction."""
from uuid import uuid4

class UnitOfWork:
    def __init__(self, db):
        self.db=db
        self.active=False
        self.owns=False
        self.savepoint='uow_'+uuid4().hex
    def __enter__(self):
        if self.active: raise RuntimeError('Unit of work already active')
        self.owns=not self.db.in_transaction
        if self.owns:
            read_only=bool(self.db.execute('PRAGMA query_only').fetchone()[0])
            self.db.execute('BEGIN' if read_only else 'BEGIN IMMEDIATE')
        try:self.db.execute('SAVEPOINT '+self.savepoint)
        except Exception:
            if self.owns:self.db.rollback()
            raise
        self.active=True
        return self
    def rollback(self):
        if not self.active:return
        try:
            self.db.execute('ROLLBACK TO '+self.savepoint)
            self.db.execute('RELEASE '+self.savepoint)
        finally:
            if self.owns:self.db.rollback()
            self.active=False
    def commit(self):
        if not self.active:return
        try:
            self.db.execute('RELEASE '+self.savepoint)
            if self.owns:self.db.commit()
        except Exception:
            if self.owns:
                self.db.rollback();self.active=False
            raise
        self.active=False
    def __exit__(self, exc_type, exc, tb):
        if exc_type:self.rollback()
        else:self.commit()
        return False
