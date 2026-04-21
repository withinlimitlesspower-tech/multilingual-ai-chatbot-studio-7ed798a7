"""
Data models for user tasks in the sidebar.
Defines Task and TaskManager classes for managing chat history and tasks.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import uuid

# Configure logging
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Enumeration of possible task statuses."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class TaskType(Enum):
    """Enumeration of possible task types."""
    CHAT = "chat"
    CODE_GENERATION = "code_generation"
    MEDIA_SEARCH = "media_search"
    VOICE_GENERATION = "voice_generation"
    SURVEY = "survey"
    MULTIMEDIA_PROJECT = "multimedia_project"


@dataclass
class Task:
    """
    Data class representing a user task.
    
    Attributes:
        id: Unique identifier for the task
        title: Short title/description of the task
        task_type: Type of task (from TaskType enum)
        status: Current status of the task (from TaskStatus enum)
        created_at: Timestamp when task was created
        updated_at: Timestamp when task was last updated
        user_id: Identifier for the user who created the task
        metadata: Additional task-specific data
        messages: List of messages in this task/conversation
        tags: List of tags for categorization
        is_favorite: Whether task is marked as favorite
    """
    id: str
    title: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    is_favorite: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Task object to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the task
        """
        task_dict = asdict(self)
        task_dict['task_type'] = self.task_type.value
        task_dict['status'] = self.status.value
        task_dict['created_at'] = self.created_at.isoformat()
        task_dict['updated_at'] = self.updated_at.isoformat()
        return task_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """
        Create Task object from dictionary.
        
        Args:
            data: Dictionary containing task data
            
        Returns:
            Task object
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Convert string enums back to Enum objects
            if 'task_type' in data and isinstance(data['task_type'], str):
                data['task_type'] = TaskType(data['task_type'])
            if 'status' in data and isinstance(data['status'], str):
                data['status'] = TaskStatus(data['status'])
            
            # Convert ISO format strings back to datetime objects
            if 'created_at' in data and isinstance(data['created_at'], str):
                data['created_at'] = datetime.fromisoformat(data['created_at'])
            if 'updated_at' in data and isinstance(data['updated_at'], str):
                data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
            return cls(**data)
        except (KeyError, ValueError) as e:
            logger.error(f"Error creating Task from dict: {e}")
            raise ValueError(f"Invalid task data: {e}")
    
    def update_status(self, new_status: TaskStatus) -> None:
        """
        Update task status and refresh updated_at timestamp.
        
        Args:
            new_status: New status for the task
        """
        self.status = new_status
        self.updated_at = datetime.now()
        logger.debug(f"Task {self.id} status updated to {new_status.value}")
    
    def add_message(self, message: Dict[str, Any]) -> None:
        """
        Add a message to the task's message history.
        
        Args:
            message: Dictionary containing message data
        """
        self.messages.append(message)
        self.updated_at = datetime.now()
        logger.debug(f"Message added to task {self.id}")
    
    def get_last_message(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent message from the task.
        
        Returns:
            Last message dictionary or None if no messages
        """
        return self.messages[-1] if self.messages else None
    
    def get_message_count(self) -> int:
        """
        Get the total number of messages in the task.
        
        Returns:
            Number of messages
        """
        return len(self.messages)
    
    def add_tag(self, tag: str) -> None:
        """
        Add a tag to the task.
        
        Args:
            tag: Tag to add
        """
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now()
            logger.debug(f"Tag '{tag}' added to task {self.id}")
    
    def remove_tag(self, tag: str) -> bool:
        """
        Remove a tag from the task.
        
        Args:
            tag: Tag to remove
            
        Returns:
            True if tag was removed, False if tag wasn't found
        """
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now()
            logger.debug(f"Tag '{tag}' removed from task {self.id}")
            return True
        return False
    
    def toggle_favorite(self) -> bool:
        """
        Toggle the favorite status of the task.
        
        Returns:
            New favorite status
        """
        self.is_favorite = not self.is_favorite
        self.updated_at = datetime.now()
        logger.debug(f"Task {self.id} favorite status toggled to {self.is_favorite}")
        return self.is_favorite


class TaskManager:
    """
    Manager class for handling user tasks.
    Provides CRUD operations and task management functionality.
    """
    
    def __init__(self, storage_file: str = "tasks.json"):
        """
        Initialize TaskManager with storage file.
        
        Args:
            storage_file: Path to JSON file for task storage
        """
        self.storage_file = storage_file
        self.tasks: Dict[str, Task] = {}
        self.load_tasks()
        logger.info(f"TaskManager initialized with {len(self.tasks)} tasks")
    
    def load_tasks(self) -> None:
        """
        Load tasks from storage file.
        Creates file if it doesn't exist.
        """
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.tasks = {
                    task_id: Task.from_dict(task_data)
                    for task_id, task_data in data.items()
                }
            logger.info(f"Loaded {len(self.tasks)} tasks from {self.storage_file}")
        except FileNotFoundError:
            logger.warning(f"Storage file {self.storage_file} not found. Starting with empty task list.")
            self.tasks = {}
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.storage_file}: {e}")
            self.tasks = {}
        except Exception as e:
            logger.error(f"Unexpected error loading tasks: {e}")
            self.tasks = {}
    
    def save_tasks(self) -> bool:
        """
        Save tasks to storage file.
        
        Returns:
            True if save successful, False otherwise
        """
        try:
            tasks_dict = {
                task_id: task.to_dict()
                for task_id, task in self.tasks.items()
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(tasks_dict, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self.tasks)} tasks to {self.storage_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving tasks to {self.storage_file}: {e}")
            return False
    
    def create_task(
        self,
        title: str,
        task_type: TaskType,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Task:
        """
        Create a new task.
        
        Args:
            title: Task title/description
            task_type: Type of task
            user_id: Optional user identifier
            metadata: Optional task metadata
            tags: Optional list of tags
            
        Returns:
            Newly created Task object
        """
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            title=title,
            task_type=task_type,
            user_id=user_id,
            metadata=metadata or {},
            tags=tags or [],
            status=TaskStatus.PENDING
        )
        
        self.tasks[task_id] = task
        self.save_tasks()
        logger.info(f"Created new task: {task_id} - {title}")
        
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Retrieve a task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task object if found, None otherwise
        """
        return self.tasks.get(task_id)
    
    def get_all_tasks(
        self,
        user_id: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """
        Get all tasks, optionally filtered by criteria.
        
        Args:
            user_id: Filter by user ID
            task_type: Filter by task type
            status: Filter by status
            
        Returns:
            List of filtered Task objects
        """
        filtered_tasks = list(self.tasks.values())
        
        if user_id:
            filtered_tasks = [t for t in filtered_tasks if t.user_id == user_id]
        
        if task_type:
            filtered_tasks = [t for t in filtered_tasks if t.task_type == task_type]
        
        if status:
            filtered_tasks = [t for t in filtered_tasks if t.status == status]
        
        # Sort by updated_at descending (most recent first)
        filtered_tasks.sort(key=lambda t: t.updated_at, reverse=True)
        
        return filtered_tasks
    
    def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[Task]:
        """
        Update an existing task.
        
        Args:
            task_id: Task identifier
            title: New title (if provided)
            status: New status (if provided)
            metadata: New metadata (if provided)
            tags: New tags (if provided)
            
        Returns:
            Updated Task object if found, None otherwise
        """