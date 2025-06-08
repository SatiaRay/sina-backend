from provider.service_container import container
import traceback
import sys

def call_function(function_name: str, *args):
    """
    Dynamically calls a function from a class based on the provided name pattern.
    
    Args:
        function_name (str): Name in format "{class_name}-{method_name}"
        args (list): List of arguments to pass to the function. If a single dictionary is passed,
                    it will be unpacked as keyword arguments.
    
    Returns:
        The result of the called function or None if the function is not found
    """
    try:
        # Split the function name into class and method parts
        class_name, method_name = function_name.split('-')
        
        # Get the class instance from service container
        instance = container.make(class_name)
        if not instance:
            print(f"Class {class_name} not found in service container")
            return None
            
        # Get the method from the instance
        method = getattr(instance, method_name, None)
        if not method:
            print(f"Method {method_name} not found in class {class_name}")
            return None
            
        # If we have exactly one argument and it's a dictionary, unpack it
        if len(args) == 1 and isinstance(args[0], dict):
            return method(**args[0])
        else:
            # Otherwise call the method with the arguments as is
            return method(*args)
            
    except Exception as e:
        # Get the full exception information
        exc_type, exc_value, exc_traceback = sys.exc_info()
        stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
        
        # Print detailed error information
        print(f"Error calling function {function_name}:")
        print(f"Exception type: {exc_type.__name__}")
        print(f"Exception message: {str(e)}")
        print("Stack trace:")
        print(''.join(stack_trace))
        
        # Also print the arguments that were passed
        print(f"Arguments passed: {args}")
        
        return None
