from enum import Enum


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class TaskSortField(str, Enum):
    created_at = "created_at"
    updated_at = "updated_at"
    due_date = "due_date"
    priority = "priority"
    status = "status"
    title = "title"


class ProjectSortField(str, Enum):
    created_at = "created_at"
    updated_at = "updated_at"
    name = "name"
