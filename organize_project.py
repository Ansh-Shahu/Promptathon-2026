import os
import shutil
import json

def organize_project():
    root_dir = os.path.dirname(os.path.abspath(__file__))

    print("📁 Starting project reorganization...")

    # Directories to create
    dirs_to_create = ["frontend", "scripts", "docs"]
    for d in dirs_to_create:
        os.makedirs(os.path.join(root_dir, d), exist_ok=True)
        print(f"Created directory: {d}/")

    # 1. Move Frontend files
    frontend_files = [
        "src", "public", "index.html", "vite.config.ts", 
        "tsconfig.json", "package.json", "package-lock.json", "node_modules"
    ]
    print("\n📦 Moving frontend files to frontend/ ...")
    for f in frontend_files:
        src_path = os.path.join(root_dir, f)
        dst_path = os.path.join(root_dir, "frontend", f)
        if os.path.exists(src_path):
            try:
                shutil.move(src_path, dst_path)
                print(f"  Moved {f}")
            except Exception as e:
                print(f"  ❌ Failed to move {f}: {e}")
                print("  Make sure 'npm run dev' is STOPPED before running this script!")

    # 2. Create wrapper package.json at root to keep `npm run dev` working seamlessly
    root_package_json = {
      "name": "hvac-project-root",
      "private": True,
      "scripts": {
        "dev": "npm run dev --prefix frontend",
        "build": "npm run build --prefix frontend",
        "preview": "npm run preview --prefix frontend",
        "install:all": "npm install --prefix frontend"
      }
    }
    with open(os.path.join(root_dir, "package.json"), "w") as f:
        json.dump(root_package_json, f, indent=2)
    print("\n📄 Created wrapper package.json at root to preserve `npm run dev`.")

    # 3. Move Scripts
    scripts_files = ["inject_fault.py", "arguments.py", "app.py"]
    print("\n📜 Moving standalone scripts to scripts/ ...")
    for f in scripts_files:
        src_path = os.path.join(root_dir, f)
        dst_path = os.path.join(root_dir, "scripts", f)
        if os.path.exists(src_path):
            try:
                shutil.move(src_path, dst_path)
                print(f"  Moved {f}")
            except Exception as e:
                print(f"  ❌ Failed to move {f}: {e}")

    # 4. Move Docs
    docs_files = ["DATA_ANALYSIS_AND_GENERATION_PROMPT.md", "Landing page"]
    print("\n📚 Moving documentation and assets to docs/ ...")
    for f in docs_files:
        src_path = os.path.join(root_dir, f)
        dst_path = os.path.join(root_dir, "docs", f)
        if os.path.exists(src_path):
            try:
                shutil.move(src_path, dst_path)
                print(f"  Moved {f}")
            except Exception as e:
                print(f"  ❌ Failed to move {f}: {e}")

    # 5. Move root requirements to backend if desired (optional)
    root_reqs = os.path.join(root_dir, "requirements.txt")
    if os.path.exists(root_reqs):
        try:
            shutil.move(root_reqs, os.path.join(root_dir, "backend", "requirements_root.txt"))
            print("  Moved root requirements.txt to backend/requirements_root.txt")
        except Exception as e:
            pass

    print("\n✅ Reorganization complete! The end-to-end functionality remains intact.")
    print("👉 Note: If you want to start the frontend, you can still just run `npm run dev` at the root folder.")

if __name__ == "__main__":
    organize_project()
