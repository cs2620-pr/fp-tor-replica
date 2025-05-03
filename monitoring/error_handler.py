"""
Error handling for the onion network.
Provides error handling, logging, and recovery capabilities.
"""

import sys
import traceback
import threading
import time
from functools import wraps

from monitoring.status_monitor import StatusMonitor


class ErrorHandler:
    """
    Handles errors in the onion network.
    """
    
    def __init__(self, monitor=None):
        """
        Initialize the ErrorHandler.
        
        Args:
            monitor (StatusMonitor, optional): Monitor for logging errors.
        """
        self.monitor = monitor or StatusMonitor(name="error_handler")
        
        # Track errors
        self.errors = []
        self.errors_lock = threading.Lock()
        
        # Install a global exception hook
        self.original_excepthook = sys.excepthook
        sys.excepthook = self.global_exception_handler
    
    def global_exception_handler(self, exc_type, exc_value, exc_traceback):
        """
        Global exception handler.
        
        Args:
            exc_type: Exception type.
            exc_value: Exception value.
            exc_traceback: Exception traceback.
        """
        # Log the error
        error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self.monitor.log_critical(f"Unhandled exception: {error_message}")
        
        # Track the error
        self.track_error(exc_type, exc_value, exc_traceback)
        
        # Call the original exception hook
        self.original_excepthook(exc_type, exc_value, exc_traceback)
    
    def track_error(self, exc_type, exc_value, exc_traceback=None):
        """
        Track an error.
        
        Args:
            exc_type: Exception type.
            exc_value: Exception value.
            exc_traceback: Exception traceback.
        """
        with self.errors_lock:
            # Add the error to the list
            self.errors.append({
                "type": exc_type,
                "value": exc_value,
                "traceback": traceback.extract_tb(exc_traceback) if exc_traceback else None,
                "timestamp": time.time()
            })
            
            # Limit the list to the last 100 errors
            if len(self.errors) > 100:
                self.errors = self.errors[-100:]
    
    def get_errors(self, limit=None):
        """
        Get tracked errors.
        
        Args:
            limit (int, optional): Maximum number of errors to return. If None, all errors are returned.
            
        Returns:
            list: List of error dictionaries.
        """
        with self.errors_lock:
            if limit is None:
                return self.errors.copy()
            else:
                return self.errors[-limit:].copy()
    
    def clear_errors(self):
        """
        Clear all tracked errors.
        """
        with self.errors_lock:
            self.errors.clear()
    
    def handle_error(self, exc_type, exc_value, exc_traceback=None):
        """
        Handle an error.
        
        Args:
            exc_type: Exception type.
            exc_value: Exception value.
            exc_traceback: Exception traceback.
            
        Returns:
            bool: True if the error was handled, False otherwise.
        """
        # Track the error
        self.track_error(exc_type, exc_value, exc_traceback)
        
        # Log the error
        if exc_traceback:
            error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        else:
            error_message = f"{exc_type.__name__}: {exc_value}"
        
        self.monitor.log_error(f"Error: {error_message}")
        
        # TODO: Implement error-specific handling
        
        return False  # Indicate that the error was not fully handled
    
    def try_catch(self, func):
        """
        Decorator to catch and handle exceptions.
        
        Args:
            func: The function to wrap.
            
        Returns:
            The wrapped function.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.handle_error(type(e), e, sys.exc_info()[2])
                raise  # Re-raise the exception
        
        return wrapper
    
    def retry(self, max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
        """
        Decorator to retry a function on failure.
        
        Args:
            max_attempts (int, optional): Maximum number of attempts.
            delay (float, optional): Initial delay between attempts in seconds.
            backoff (float, optional): Backoff multiplier for the delay.
            exceptions (tuple, optional): Tuple of exceptions to catch.
            
        Returns:
            A decorator function.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                attempt = 0
                current_delay = delay
                
                while attempt < max_attempts:
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        attempt += 1
                        
                        if attempt >= max_attempts:
                            self.handle_error(type(e), e, sys.exc_info()[2])
                            raise
                        
                        self.monitor.log_warning(
                            f"Retrying {func.__name__} after error: {e} "
                            f"(attempt {attempt}/{max_attempts})"
                        )
                        
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            return wrapper
        
        return decorator
    
    def timeout(self, seconds):
        """
        Decorator to apply a timeout to a function.
        
        Args:
            seconds (float): Timeout in seconds.
            
        Returns:
            A decorator function.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Define a wrapper function to run in a separate thread
                result = [None]
                exception = [None]
                
                def worker():
                    try:
                        result[0] = func(*args, **kwargs)
                    except Exception as e:
                        exception[0] = e
                
                # Start a thread to run the function
                thread = threading.Thread(target=worker)
                thread.daemon = True
                thread.start()
                
                # Wait for the thread to complete
                thread.join(seconds)
                
                # Check if the thread is still alive (timeout occurred)
                if thread.is_alive():
                    self.monitor.log_warning(
                        f"Timeout of {seconds} seconds exceeded for {func.__name__}"
                    )
                    raise TimeoutError(f"Timeout of {seconds} seconds exceeded for {func.__name__}")
                
                # Re-raise any exception that occurred
                if exception[0] is not None:
                    raise exception[0]
                
                return result[0]
            
            return wrapper
        
        return decorator


# Singleton instance
_global_error_handler = None


def get_global_error_handler():
    """
    Get the global ErrorHandler instance.
    
    Returns:
        ErrorHandler: The global error handler instance.
    """
    global _global_error_handler
    
    if _global_error_handler is None:
        from monitoring.status_monitor import get_global_monitor
        _global_error_handler = ErrorHandler(monitor=get_global_monitor())
    
    return _global_error_handler


def try_catch(func):
    """
    Decorator to catch and handle exceptions using the global error handler.
    
    Args:
        func: The function to wrap.
        
    Returns:
        The wrapped function.
    """
    return get_global_error_handler().try_catch(func)


def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Decorator to retry a function on failure using the global error handler.
    
    Args:
        max_attempts (int, optional): Maximum number of attempts.
        delay (float, optional): Initial delay between attempts in seconds.
        backoff (float, optional): Backoff multiplier for the delay.
        exceptions (tuple, optional): Tuple of exceptions to catch.
        
    Returns:
        A decorator function.
    """
    return get_global_error_handler().retry(max_attempts, delay, backoff, exceptions)


def timeout(seconds):
    """
    Decorator to apply a timeout to a function using the global error handler.
    
    Args:
        seconds (float): Timeout in seconds.
        
    Returns:
        A decorator function.
    """
    return get_global_error_handler().timeout(seconds)


if __name__ == "__main__":
    # Test the ErrorHandler
    handler = ErrorHandler()
    
    # Test the try_catch decorator
    @handler.try_catch
    def test_try_catch():
        print("Testing try_catch decorator")
        raise ValueError("Test error")
    
    try:
        test_try_catch()
    except ValueError:
        print("Caught ValueError as expected")
    
    # Test the retry decorator
    @handler.retry(max_attempts=3, delay=0.1)
    def test_retry(succeed_on_attempt):
        print(f"Testing retry decorator (attempt {test_retry.attempt})")
        test_retry.attempt += 1
        
        if test_retry.attempt < succeed_on_attempt:
            raise ValueError(f"Failing on attempt {test_retry.attempt}")
        
        return "Success"
    
    test_retry.attempt = 0
    result = test_retry(3)
    print(f"Result: {result}")
    
    # Test the timeout decorator
    @handler.timeout(1)
    def test_timeout(sleep_time):
        print(f"Testing timeout decorator (sleeping for {sleep_time} seconds)")
        time.sleep(sleep_time)
        return "Success"
    
    try:
        result = test_timeout(0.5)
        print(f"Result: {result}")
    except TimeoutError:
        print("Unexpected timeout")
    
    try:
        result = test_timeout(2)
        print(f"Result: {result}")
    except TimeoutError:
        print("Caught TimeoutError as expected")
    
    # Print tracked errors
    print("\nTracked errors:")
    for i, error in enumerate(handler.get_errors()):
        print(f"{i+1}. {error['type'].__name__}: {error['value']}")
