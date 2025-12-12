# app/logger.py
"""
Structured logging configuration for the application.
Provides JSON logging for production and pretty console logging for development.
"""
import structlog
import logging
import sys
import os
from typing import Any

def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    
    # Determine if we're in production or development
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        stream=sys.stdout
    )
    
    # Define processors based on environment
    processors = [
        # Add contextvars (for request IDs, etc.)
        structlog.contextvars.merge_contextvars,
        
        # Add log level to each log entry
        structlog.processors.add_log_level,
        
        # Add logger name
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        
        # Add stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        
        # Format exceptions
        structlog.processors.format_exc_info,
        
        # Decode unicode
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Add appropriate renderer based on environment
    if is_production or not sys.stderr.isatty():
        # JSON logging for production/non-TTY environments
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Pretty console logging for development
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback
            )
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True
    )


def get_logger(name: str = __name__) -> Any:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__ of the calling module)
        
    Returns:
        Configured structlog logger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_created", user_id=123, email="user@example.com")
    """
    return structlog.get_logger(name)


# Convenience function to bind context globally
def bind_context(**kwargs) -> None:
    """
    Bind context variables that will be included in all subsequent log messages.
    
    Args:
        **kwargs: Key-value pairs to bind to the logging context
        
    Example:
        >>> bind_context(request_id="abc-123", user_id=456)
        >>> logger.info("processing_request")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


def unbind_context(*keys) -> None:
    """
    Remove specific keys from the logging context.
    
    Args:
        *keys: Keys to remove from the context
    """
    structlog.contextvars.unbind_contextvars(*keys)


# Example usage and logging helpers
class LoggerMixin:
    """
    Mixin class to add logging capabilities to any class.
    
    Usage:
        class MyService(LoggerMixin):
            def do_something(self):
                self.logger.info("doing_something", param="value")
    """
    
    @property
    def logger(self):
        """Get a logger instance for this class."""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger
