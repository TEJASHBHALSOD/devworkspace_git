from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models.project import Project, NormalFile

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    # Fetch user metrics for dashboard cards
    total_projects = Project.query.filter_by(user_id=current_user.id).count()
    active_projects = Project.query.filter_by(user_id=current_user.id, status='active').count()
    total_files = NormalFile.query.filter_by(user_id=current_user.id).count()
    recent_projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.updated_at.desc()).limit(5).all()

    return render_template(
        'dashboard/index.html',
        total_projects=total_projects,
        active_projects=active_projects,
        total_files=total_files,
        recent_projects=recent_projects
    )
@dashboard_bp.route('/workspace')
@login_required
def workspace():
    return render_template('dashboard/workspace.html')

@dashboard_bp.route('/projects')
@login_required
def projects():
    return render_template('dashboard/projects.html')

@dashboard_bp.route('/courses')
@login_required
def courses():
    return render_template('dashboard/courses.html')

@dashboard_bp.route('/languages')
@login_required
def languages():
    return render_template('dashboard/languages.html')