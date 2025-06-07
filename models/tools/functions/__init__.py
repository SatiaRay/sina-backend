from provider.service_container import container

def call_function(function_name: str, *args):
    """
    Dynamically calls a function from a class based on the provided name pattern.
    
    Args:
        function_name (str): Name in format "{class_name}-{method_name}"
        args (list): List of arguments to pass to the function
    
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
            
        # Call the method with the provided arguments
        return method(*args)
    except Exception as e:
        print(f"Error calling function {function_name}: {str(e)}")
        return None
