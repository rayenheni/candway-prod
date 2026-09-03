
import os
import py_compile

def check_syntax(start_path):
    for root, dirs, files in os.walk(start_path):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    py_compile.compile(path, doraise=True)
                    # print(f"OK: {path}")
                except py_compile.PyCompileError as e:
                    print(f"SYNTAX ERROR in {path}")
                    print(e)
                except Exception as e:
                    print(f"Error checking {path}: {e}")

if __name__ == "__main__":
    print("Checking syntax...")
    check_syntax("backend")
    print("Done.")
