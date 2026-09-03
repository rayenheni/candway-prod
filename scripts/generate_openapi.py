
import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment to dev for generation if needed, or rely on .env
os.environ["ENVIRONMENT"] = "development"

from backend.app import create_app

def generate_openapi():
    print("Initializing app...")
    app = create_app()
    print("Generating schema...")
    openapi_schema = app.openapi()
    
    # Save to file
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "openapi.json")
    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)
    
    print(f"OpenAPI schema generated at {output_path}")

if __name__ == "__main__":
    generate_openapi()
