import os
import requests
import git
import shutil

# --- CONFIGURATION ---

# Source (gitlab.com)
SRC_GITLAB_URL = "MIGRATION FROM"
SRC_GROUP_NAME = "XXXXXXXXXXX"
SRC_ACCESS_TOKEN = "XXXXXXXXXXX"  # Replace with your token

# Destination (self-hosted)
DEST_GITLAB_URL = "MIGRATION TO"
DEST_GROUP_NAME = "XXXXXXXXXXX"
DEST_ACCESS_TOKEN = "XXXXXXXXXXX"  # Replace with your token

# Temporary working directory
CLONE_DIR = "temp_repos"
os.makedirs(CLONE_DIR, exist_ok=True)


# --- FUNCTIONS ---

def get_group_id(base_url, group_name, token):
    response = requests.get(
        f"{base_url}/api/v4/groups/{group_name}",
        headers={"PRIVATE-TOKEN": token}
    )
    response.raise_for_status()
    return response.json()["id"]


def list_group_projects(base_url, group_id, token):
    projects = []
    page = 1
    while True:
        response = requests.get(
            f"{base_url}/api/v4/groups/{group_id}/projects",
            headers={"PRIVATE-TOKEN": token},
            params={"per_page": 100, "page": page}
        )
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        projects.extend(data)
        page += 1
    return projects


def create_project_on_dest(name, path):
    group_id = get_group_id(DEST_GITLAB_URL, DEST_GROUP_NAME, DEST_ACCESS_TOKEN)
    response = requests.post(
        f"{DEST_GITLAB_URL}/api/v4/projects",
        headers={"PRIVATE-TOKEN": DEST_ACCESS_TOKEN},
        json={
            "name": name,
            "path": path,
            "namespace_id": group_id,
            "visibility": "private"
        }
    )
    if response.status_code == 400 and "has already been taken" in response.text:
        print(f"Project {name} already exists, continuing...")
        return f"{DEST_GITLAB_URL}/{DEST_GROUP_NAME}/{path}.git"
    response.raise_for_status()
    return response.json()["http_url_to_repo"]


def mirror_repo(src_url, dest_url, repo_name):
    print(f"\n📦 Cloning: {repo_name}")
    local_path = os.path.join(CLONE_DIR, repo_name)
    repo = git.Repo.clone_from(src_url, local_path, mirror=True)

    print(f"🚀 Pushing to destination...")
    repo.create_remote("dest", url=dest_url)
    repo.remotes.dest.push(mirror=True)

    shutil.rmtree(local_path)


# --- MAIN LOGIC ---

print("🔍 Fetching projects from source GitLab...")
src_group_id = get_group_id(SRC_GITLAB_URL, SRC_GROUP_NAME, SRC_ACCESS_TOKEN)
projects = list_group_projects(SRC_GITLAB_URL, src_group_id, SRC_ACCESS_TOKEN)

for project in projects:
    name = project["name"]
    path = project["path"]
    print(f"\n=== 🚚 Migrating: {name} ===")

    # Construct authenticated clone URL (source)
    src_url = f"https://oauth2:{SRC_ACCESS_TOKEN}@gitlab.com/{SRC_GROUP_NAME}/{path}.git"

    # Create project in destination and get destination URL
    dest_url_clean = create_project_on_dest(name, path)
    dest_url = dest_url_clean.replace("https://", f"https://oauth2:{DEST_ACCESS_TOKEN}@")

    # Mirror push
    try:
        mirror_repo(src_url, dest_url, name)
    except Exception as e:
        print(f"❌ Error pushing {name}: {e}")

print("\n✅ Migration complete.")
