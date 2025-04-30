"""
Status monitoring for the onion network.
Provides logging and performance monitoring capabilities.
"""

import os
import logging
import threading
import time
from datetime import datetime


class StatusMonitor:
    """
    Monitor for tracking the status of onion network components.
    """
    
    # Log levels
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL
    
    def __init__(self, name=None, log_level=logging.INFO, log_to_file=True):
        """
        Initialize the StatusMonitor.
        
        Args:
            name (str, optional): Name for this monitor. If None, a name is generated.
            log_level (int, optional): Logging level.
            log_to_file (bool, optional): Whether to log to a file.
        """
        # Generate a name if none is provided
        if name is None:
            name = f"onion_{threading.current_thread().name}_{int(time.time())}"
        
        self.name = name
        self.log_level = log_level
        self.log_to_file = log_to_file
        
        # Metrics storage
        self.metrics = {}
        self.metrics_lock = threading.Lock()
        
        # Set up logging
        self._setup_logging()
    
    def _setup_logging(self):
        """
        Set up logging for this monitor.
        """
        # Create the logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.log_level)
        
        # Remove any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create a formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create a console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Create a file handler if requested
        if self.log_to_file:
            # Create the logs directory if it doesn't exist
            os.makedirs("logs", exist_ok=True)
            
            # Create a file handler with the current date and time
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"logs/{self.name}_{timestamp}.log"
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(self.log_level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def log(self, level, message):
        """
        Log a message at the specified level.
        
        Args:
            level (int): Logging level.
            message (str): Message to log.
        """
        self.logger.log(level, message)
    
    def log_debug(self, message):
        """
        Log a debug message.
        
        Args:
            message (str): Message to log.
        """
        self.logger.debug(message)
    
    def log_info(self, message):
        """
        Log an info message.
        
        Args:
            message (str): Message to log.
        """
        self.logger.info(message)
    
    def log_warning(self, message):
        """
        Log a warning message.
        
        Args:
            message (str): Message to log.
        """
        self.logger.warning(message)
    
    def log_error(self, message):
        """
        Log an error message.
        
        Args:
            message (str): Message to log.
        """
        self.logger.error(message)
    
    def log_critical(self, message):
        """
        Log a critical message.
        
        Args:
            message (str): Message to log.
        """
        self.logger.critical(message)
    
    def track_metric(self, name, value):
        """
        Track a metric.
        
        Args:
            name (str): Name of the metric.
            value: Value of the metric.
        """
        with self.metrics_lock:
            # Add the value to the metric history
            if name not in self.metrics:
                self.metrics[name] = []
            
            # Add a timestamp and value
            self.metrics[name].append((time.time(), value))
            
            # Limit the history to the last 1000 values
            if len(self.metrics[name]) > 1000:
                self.metrics[name] = self.metrics[name][-1000:]
    
    def get_metric(self, name):
        """
        Get the current value of a metric.
        
        Args:
            name (str): Name of the metric.
            
        Returns:
            The most recent value of the metric, or None if the metric doesn't exist.
        """
        with self.metrics_lock:
            if name in self.metrics and self.metrics[name]:
                return self.metrics[name][-1][1]
            
            return None
    
    def get_metric_history(self, name, limit=None):
        """
        Get the history of a metric.
        
        Args:
            name (str): Name of the metric.
            limit (int, optional): Maximum number of values to return. If None, all values are returned.
            
        Returns:
            list: List of (timestamp, value) tuples, or an empty list if the metric doesn't exist.
        """
        with self.metrics_lock:
            if name in self.metrics:
                if limit is None:
                    return self.metrics[name]
                else:
                    return self.metrics[name][-limit:]
            
            return []
    
    def get_metrics(self):
        """
        Get all metrics.
        
        Returns:
            dict: Dictionary mapping metric names to their most recent values.
        """
        result = {}
        
        with self.metrics_lock:
            for name, history in self.metrics.items():
                if history:
                    result[name] = history[-1][1]
        
        return result
    
    def reset_metrics(self):
        """
        Reset all metrics.
        """
        with self.metrics_lock:
            self.metrics.clear()
    
    def start_performance_tracking(self, interval=60):
        """
        Start tracking performance metrics.
        
        Args:
            interval (int, optional): Interval in seconds between measurements.
        """
        # Create a thread to track performance metrics
        thread = threading.Thread(
            target=self._track_performance,
            args=(interval,),
            daemon=True
        )
        thread.start()
    
    def _track_performance(self, interval):
        """
        Track performance metrics.
        
        Args:
            interval (int): Interval in seconds between measurements.
        """
        import psutil
        
        while True:
            try:
                # Get CPU usage
                cpu_usage = psutil.cpu_percent(interval=1)
                self.track_metric("cpu_usage", cpu_usage)
                
                # Get memory usage
                memory_usage = psutil.virtual_memory().percent
                self.track_metric("memory_usage", memory_usage)
                
                # Get network I/O
                net_io = psutil.net_io_counters()
                self.track_metric("bytes_sent", net_io.bytes_sent)
                self.track_metric("bytes_recv", net_io.bytes_recv)
                
                # Get disk I/O
                disk_io = psutil.disk_io_counters()
                self.track_metric("disk_read", disk_io.read_bytes)
                self.track_metric("disk_write", disk_io.write_bytes)
                
                # Sleep for the specified interval
                time.sleep(interval)
            
            except Exception as e:
                self.log_error(f"Failed to track performance: {e}")
                time.sleep(interval)


# Singleton instance
_global_monitor = None


def get_global_monitor():
    """
    Get the global StatusMonitor instance.
    
    Returns:
        StatusMonitor: The global monitor instance.
    """
    global _global_monitor
    
    if _global_monitor is None:
        _global_monitor = StatusMonitor(name="global")
    
    return _global_monitor


if __name__ == "__main__":
    # Test the StatusMonitor
    monitor = StatusMonitor(name="test", log_level=logging.DEBUG)
    
    # Log some messages
    monitor.log_debug("This is a debug message")
    monitor.log_info("This is an info message")
    monitor.log_warning("This is a warning message")
    monitor.log_error("This is an error message")
    monitor.log_critical("This is a critical message")
    
    # Track some metrics
    for i in range(10):
        monitor.track_metric("test_metric", i)
        time.sleep(0.1)
    
    # Get metric values
    print(f"Current value: {monitor.get_metric('test_metric')}")
    print(f"History: {monitor.get_metric_history('test_metric', limit=5)}")
    print(f"All metrics: {monitor.get_metrics()}")
    
    # Start performance tracking if psutil is available
    try:
        import psutil
        monitor.start_performance_tracking(interval=5)
        
        # Wait for some data to be collected
        print("Collecting performance metrics...")
        time.sleep(10)
        
        # Print performance metrics
        print(f"CPU usage: {monitor.get_metric('cpu_usage')}%")
        print(f"Memory usage: {monitor.get_metric('memory_usage')}%")
        print(f"Bytes sent: {monitor.get_metric('bytes_sent')}")
        print(f"Bytes received: {monitor.get_metric('bytes_recv')}")
    
    except ImportError:
        print("psutil not available, skipping performance tracking")
    
    # Reset metrics
    monitor.reset_metrics()
    print(f"After reset: {monitor.get_metrics()}")
