import os
from pathlib import Path
from flask import current_app

class StorageService:
    @staticmethod
    def get_user_root(user_id: int) -> Path:
        """Returns isolated user directory path."""
        user_dir = current_app.config["USERS_DIR"] / f"User_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir.resolve()

    @staticmethod
    def resolve_safe_path(user_id: int, relative_path: str, is_project: bool = True) -> Path:
        """
        Prevents Path Traversal vulnerabilities (e.g., ../../etc/passwd)
        by enforcing strict resolving relative to authorized root directories.
        """
        user_root = StorageService.get_user_root(user_id)
        sub_folder = "Projects" if is_project else "Normal_Files"
        base_dir = (user_root / sub_folder).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)

        # Strip dangerous leading slashes or Windows drives
        clean_relative = os.path.normpath(relative_path).lstrip("/\\")
        target_path = (base_dir / clean_relative).resolve()

        if not str(target_path).startswith(str(base_dir)):
            raise PermissionError("Access Denied: Path Traversal Detected")

        return target_path