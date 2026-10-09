from datetime import datetime
from models import db

class ProjectTemplate(db.Model):
    __tablename__ = 'project_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(50), nullable=False) # Python, HTML, CSS, JavaScript
    project_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    template_structure = db.Column(db.JSON, nullable=False) # Directory tree JSON schema
    entry_file = db.Column(db.String(255), default="main.py")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey('project_templates.id', ondelete='SET NULL'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    language = db.Column(db.String(50), nullable=False)
    project_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    root_path = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default="active") # active, archived
    entry_file = db.Column(db.String(255), default="main.py")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship for file metadata tracking
    files = db.relationship('ProjectFile', backref='project', lazy=True, cascade="all, delete-orphan")

class ProjectFile(db.Model):
    __tablename__ = 'project_files'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    relative_path = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    is_directory = db.Column(db.Boolean, default=False)
    size = db.Column(db.Integer, default=0) # Size in bytes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class NormalFile(db.Model):
    __tablename__ = 'normal_files'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False) # Documents, Images, Notes, Other
    relative_path = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)