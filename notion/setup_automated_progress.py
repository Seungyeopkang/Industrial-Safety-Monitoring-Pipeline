import os
import sys
import requests
from dotenv import load_dotenv

# 프로젝트 루트 기준 .env 로드 (하드코딩된 절대경로 제거)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
SPRINT_TASKS_DB_ID = os.getenv("NOTION_SPRINT_DB_ID")

if not NOTION_API_KEY or NOTION_API_KEY == "your_notion_api_key":
    print("Error: NOTION_API_KEY가 .env 파일에 올바르게 설정되지 않았습니다.")
    sys.exit(1)
if not NOTION_PAGE_ID or NOTION_PAGE_ID == "your_notion_page_id":
    print("Error: NOTION_PAGE_ID가 .env 파일에 올바르게 설정되지 않았습니다.")
    sys.exit(1)
if not SPRINT_TASKS_DB_ID:
    print("Error: NOTION_SPRINT_DB_ID가 .env 파일에 설정되지 않았습니다.")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def create_manager_db():
    print("Creating Sprint Manager Database with Relation and Rollup...")
    url = "https://api.notion.com/v1/databases"
    payload = {
        "parent": {
            "type": "page_id",
            "page_id": NOTION_PAGE_ID
        },
        "title": [
            {
                "type": "text",
                "text": {"content": "📊 스프린트 및 전체 진행률 (자동 업데이트)"}
            }
        ],
        "properties": {
            "이름": {"title": {}},
            "Tasks": {
                "relation": {
                    "database_id": SPRINT_TASKS_DB_ID,
                    "single_property": {}
                }
            },
            "Progress": {
                "rollup": {
                    "relation_property_name": "Tasks",
                    "rollup_property_name": "Completed",
                    "function": "percent_checked"
                }
            }
        }
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        db_id = response.json().get("id")
        print(f"Success! Manager DB created: {db_id}")
        return db_id
    else:
        print("Failed to create Manager DB:", response.text)
        return None

def fetch_all_tasks():
    print("Fetching all tasks from Sprint Plan...")
    url = f"https://api.notion.com/v1/databases/{SPRINT_TASKS_DB_ID}/query"
    response = requests.post(url, headers=headers)
    if response.status_code != 200:
        print("Failed to fetch tasks:", response.text)
        return []
    return response.json().get("results", [])

def populate_manager_db(manager_db_id, tasks):
    print("Populating Manager DB with Overall and per-Sprint pages...")
    
    # Group tasks by Sprint
    sprints = {}
    all_task_ids = []
    
    for task in tasks:
        task_id = task["id"]
        all_task_ids.append(task_id)
        
        props = task.get("properties", {})
        sprint_name = "기타"
        if "Sprint" in props and props["Sprint"].get("select"):
            sprint_name = props["Sprint"]["select"]["name"]
            
        if sprint_name not in sprints:
            sprints[sprint_name] = []
        sprints[sprint_name].append(task_id)
        
    url = "https://api.notion.com/v1/pages"
    
    # 1. Create Overall Project Page
    print("Creating '전체 프로젝트' progress tracker...")
    payload = {
        "parent": {"database_id": manager_db_id},
        "properties": {
            "이름": {"title": [{"text": {"content": "🔥 전체 프로젝트"}}]},
            "Tasks": {"relation": [{"id": tid} for tid in all_task_ids]}
        }
    }
    requests.post(url, json=payload, headers=headers)
    
    # 2. Create individual Sprint Pages
    for sprint_name, t_ids in sprints.items():
        print(f"Creating '{sprint_name}' progress tracker...")
        payload = {
            "parent": {"database_id": manager_db_id},
            "properties": {
                "이름": {"title": [{"text": {"content": sprint_name}}]},
                "Tasks": {"relation": [{"id": tid} for tid in t_ids]}
            }
        }
        requests.post(url, json=payload, headers=headers)
        
    print("All progress trackers successfully created and linked!")

if __name__ == "__main__":
    db_id = create_manager_db()
    if db_id:
        tasks = fetch_all_tasks()
        if tasks:
            populate_manager_db(db_id, tasks)
