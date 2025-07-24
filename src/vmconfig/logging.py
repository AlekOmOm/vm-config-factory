"""Logging configuration and utilities"""
import logging
import sys
from pathlib import Path
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console

def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    console: Optional[Console] = None
) -> logging.Logger:
    """Setup logging with Rich formatting and optional file output"""
    
    # Create logger
    logger = logging.getLogger("vmconfig")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with Rich formatting
    if console is None:
        console = Console()
    
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True
    )
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # Format for console
    console_format = "%(message)s"
    console_handler.setFormatter(logging.Formatter(console_format))
    
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always debug level for files
        
        # More detailed format for file
        file_format = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        file_handler.setFormatter(logging.Formatter(file_format))
        
        logger.addHandler(file_handler)
    
    return logger

def get_logger(name: str = "vmconfig") -> logging.Logger:
    """Get configured logger instance"""
    return logging.getLogger(name)

class ProgressLogger:
    """Logger that integrates with Rich progress bars"""
    
    def __init__(self, logger: logging.Logger, progress=None):
        self.logger = logger
        self.progress = progress
        self.current_task = None
    
    def start_task(self, description: str, total: Optional[int] = None):
        """Start a new progress task"""
        if self.progress:
            self.current_task = self.progress.add_task(description, total=total)
        self.logger.info(f"Started: {description}")
    
    def update_task(self, description: str = None, advance: int = 1):
        """Update current progress task"""
        if self.progress and self.current_task is not None:
            if description:
                self.progress.update(self.current_task, description=description)
            self.progress.advance(self.current_task, advance)
    
    def complete_task(self, description: str = None):
        """Complete current progress task"""
        if description:
            self.logger.info(f"Completed: {description}")
        if self.progress and self.current_task is not None:
            self.progress.update(self.current_task, completed=True)
            self.current_task = None
    
    def error(self, message: str, exception: Exception = None):
        """Log error and update progress"""
        if exception:
            self.logger.error(f"{message}: {exception}")
        else:
            self.logger.error(message)
        
        if self.progress and self.current_task is not None:
            self.progress.update(self.current_task, description=f"❌ {message}")

def log_execution_context(logger: logging.Logger, **context):
    """Log execution context for debugging"""
    logger.debug("Execution context:")
    for key, value in context.items():
        logger.debug(f"  {key}: {value}")
