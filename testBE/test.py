import crawl4ai
import inspect

print("crawl4ai version:", crawl4ai.__version__)

print("\nAll attributes in the crawl4ai module:")
for attr_name in dir(crawl4ai):
    if not attr_name.startswith('__'):
        attr = getattr(crawl4ai, attr_name)
        attr_type = type(attr).__name__
        print(f"- {attr_name}: {attr_type}")
        
        if inspect.isclass(attr) or inspect.isfunction(attr):
            try:
                print(f"  Signature: {inspect.signature(attr)}")
            except ValueError:
                print("  Signature: Cannot determine")