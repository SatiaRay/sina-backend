from typing import Any, Dict, Type, Optional, Callable
from functools import wraps
import importlib
import inspect
from pathlib import Path

class ServiceContainer:
    """
    A simple service container implementation for dependency injection and mocking.
    Similar to Laravel's service container but simplified for Python.
    """
    _instance = None
    _bindings: Dict[str, Any] = {}
    _singletons: Dict[str, Any] = {}
    _aliases: Dict[str, str] = {}
    _base_path: Optional[Path] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceContainer, cls).__new__(cls)
        return cls._instance

    @classmethod
    def set_base_path(cls, path: str) -> None:
        """
        Set the base path for auto-loading classes.
        
        Args:
            path: The base path of your project
        """
        cls._base_path = Path(path)

    def _convert_to_module_path(self, abstract: str) -> str:
        """
        Convert a dot-notation path to a Python module path.
        
        Args:
            abstract: The dot-notation path (e.g., 'database.repository.WorkflowRepository')
            
        Returns:
            The Python module path
        """
        parts = abstract.split('.')
        if len(parts) < 2:
            return abstract
            
        # Convert to snake_case for file path
        module_path = '.'.join(parts[:-1])
        class_name = parts[-1]
        
        return f"{module_path}.{class_name}"

    def _auto_load_class(self, abstract: str) -> Any:
        """
        Automatically load and instantiate a class based on its namespace path.
        
        Args:
            abstract: The dot-notation path to the class
            
        Returns:
            The instantiated class
            
        Raises:
            ImportError: If the class cannot be imported
            ValueError: If the class cannot be instantiated
        """
        try:
            # Convert to module path
            module_path = self._convert_to_module_path(abstract)
            
            # Split into module and class name
            module_name, class_name = module_path.rsplit('.', 1)
            
            # Import the module
            module = importlib.import_module(module_name)
            
            # Get the class
            class_obj = getattr(module, class_name)
            
            # Check if it's a class
            if not inspect.isclass(class_obj):
                raise ValueError(f"{class_name} is not a class")
                
            # Create an instance
            instance = class_obj()
            
            # Register as singleton
            self.singleton(abstract, lambda: instance)
            
            return instance
            
        except ImportError as e:
            raise ImportError(f"Could not import {abstract}: {str(e)}")
        except AttributeError as e:
            raise ValueError(f"Could not find class {class_name} in module {module_name}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error auto-loading {abstract}: {str(e)}")

    def bind(self, abstract: str, concrete: Any, shared: bool = False) -> None:
        """
        Bind an abstract type to a concrete implementation.
        
        Args:
            abstract: The abstract type or interface name
            concrete: The concrete implementation or factory function
            shared: Whether to treat the binding as a singleton
        """
        self._bindings[abstract] = {
            'concrete': concrete,
            'shared': shared
        }

    def singleton(self, abstract: str, concrete: Any) -> None:
        """
        Register a shared binding in the container.
        
        Args:
            abstract: The abstract type or interface name
            concrete: The concrete implementation or factory function
        """
        self.bind(abstract, concrete, shared=True)

    def alias(self, alias: str, abstract: str) -> None:
        """
        Register an alias for an abstract type.
        
        Args:
            alias: The alias name
            abstract: The abstract type to alias
        """
        self._aliases[alias] = abstract

    def make(self, abstract: str, *args, **kwargs) -> Any:
        """
        Resolve the given type from the container.
        
        Args:
            abstract: The abstract type to resolve
            *args: Positional arguments to pass to the concrete implementation
            **kwargs: Keyword arguments to pass to the concrete implementation
            
        Returns:
            The resolved instance
        """
        # Resolve alias if exists
        abstract = self._aliases.get(abstract, abstract)

        # Check if we have a binding
        if abstract not in self._bindings:
            try:
                # Try to auto-load the class
                return self._auto_load_class(abstract)
            except (ImportError, ValueError) as e:
                raise ValueError(f"No binding found for {abstract} and auto-loading failed: {str(e)}")

        binding = self._bindings[abstract]

        # If it's a shared binding and we already have an instance, return it
        if binding['shared'] and abstract in self._singletons:
            return self._singletons[abstract]

        # Get the concrete implementation
        concrete = binding['concrete']

        # If concrete is a callable, call it
        if callable(concrete):
            instance = concrete(*args, **kwargs)
        else:
            instance = concrete

        # If it's a shared binding, store the instance
        if binding['shared']:
            self._singletons[abstract] = instance

        return instance

    def instance(self, abstract: str, instance: Any) -> None:
        """
        Register an existing instance as shared in the container.
        
        Args:
            abstract: The abstract type to bind the instance to
            instance: The instance to bind
        """
        self._singletons[abstract] = instance
        self.bind(abstract, lambda: instance, shared=True)

    def forget_instance(self, abstract: str) -> None:
        """
        Remove an instance from the container.
        
        Args:
            abstract: The abstract type to remove
        """
        if abstract in self._singletons:
            del self._singletons[abstract]

    def forget_instances(self) -> None:
        """
        Remove all instances from the container.
        """
        self._singletons.clear()

    def flush(self) -> None:
        """
        Remove all bindings and instances from the container.
        """
        self._bindings.clear()
        self._singletons.clear()
        self._aliases.clear()

# Create a global container instance
container = ServiceContainer()

def inject(abstract: str):
    """
    Decorator to inject dependencies into functions.
    
    Args:
        abstract: The abstract type to inject
        
    Returns:
        Decorated function with injected dependency
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            instance = container.make(abstract)
            return func(instance, *args, **kwargs)
        return wrapper
    return decorator 