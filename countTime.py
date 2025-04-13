import time

def count_seconds(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        seconds_elapsed = end_time - start_time
        print(f"{func} took {seconds_elapsed} seconds.")
        return result
    return wrapper