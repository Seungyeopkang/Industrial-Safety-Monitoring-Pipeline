import os
import requests
from dotenv import load_dotenv

env_path = r"c:\Users\user\Desktop\VLM-Based Industrial Safety Monitoring Pipeline\.env"
load_dotenv(dotenv_path=env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def mark_task_completed(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Completed": {
                "checkbox": True
            }
        }
    }
    res = requests.patch(url, json=payload, headers=headers)
    if res.status_code == 200:
        print(f"Successfully marked task {page_id} as completed!")
    else:
        print(f"Failed to update task {page_id}:", res.text)

if __name__ == "__main__":
    # Page IDs for Task 1 and Task 2
    task1_id = "38e73d49-32e0-8184-b2a4-f2e72c409e5c"
    task2_id = "38e73d49-32e0-818b-8de2-ff2827d599e6"
    
    print("Updating Task 1 to completed...")
    mark_task_completed(task1_id)
    
    print("Updating Task 2 to completed...")
    mark_task_completed(task2_id)
