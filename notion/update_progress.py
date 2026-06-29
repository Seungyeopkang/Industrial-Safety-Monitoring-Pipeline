import os
import requests
from dotenv import load_dotenv
from collections import defaultdict

# 환경변수 로드
env_path = r"c:\Users\user\Desktop\VLM-Based Industrial Safety Monitoring Pipeline\.env"
load_dotenv(dotenv_path=env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
# Sprint 계획 데이터베이스 ID (하드코딩 혹은 환경변수)
SPRINT_DB_ID = "38e73d49-32e0-812e-8adf-e6d1b67876c4" 

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def generate_progress_bar(percentage, length=20):
    filled = int((percentage / 100) * length)
    empty = length - filled
    return "█" * filled + "░" * empty + f" {percentage:.1f}%"

def get_sprint_progress():
    url = f"https://api.notion.com/v1/databases/{SPRINT_DB_ID}/query"
    
    # 페이징 처리 없이 일단 100개까지 가져옴 (현재 태스크 약 30개)
    response = requests.post(url, headers=headers)
    if response.status_code != 200:
        print("Error fetching tasks:", response.text)
        return None, None
        
    tasks = response.json().get("results", [])
    
    total_tasks = len(tasks)
    total_completed = 0
    
    sprint_stats = defaultdict(lambda: {"total": 0, "completed": 0})
    
    for task in tasks:
        props = task.get("properties", {})
        
        # 완료 여부 파악
        completed = False
        if "Completed" in props and props["Completed"].get("checkbox") is True:
            completed = True
            total_completed += 1
            
        # 스프린트 이름 파악
        sprint_name = "기타"
        if "Sprint" in props and props["Sprint"].get("select"):
            sprint_name = props["Sprint"]["select"]["name"]
            
        sprint_stats[sprint_name]["total"] += 1
        if completed:
            sprint_stats[sprint_name]["completed"] += 1
            
    # 전체 진행률 계산
    overall_pct = (total_completed / total_tasks * 100) if total_tasks > 0 else 0
    
    # 스프린트별 정렬 (이름 기준)
    sorted_sprints = sorted(sprint_stats.items(), key=lambda x: x[0])
    
    return overall_pct, sorted_sprints

def update_dashboard():
    overall_pct, sorted_sprints = get_sprint_progress()
    if overall_pct is None:
        return
        
    # 1. 기존 진행률 블록 지우기 (대시보드 페이지 자식 검색)
    child_url = f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children"
    response = requests.get(child_url, headers=headers)
    if response.status_code == 200:
        blocks = response.json().get("results", [])
        delete_mode = False
        for block in blocks:
            # "진행률 (Progress)" 헤더를 찾으면 그 이후 블록들을 삭제
            if block["type"] == "heading_2":
                text = block["heading_2"]["rich_text"][0]["text"]["content"] if block["heading_2"]["rich_text"] else ""
                if "진행률 (Progress)" in text or "전체 프로젝트 진행률" in text:
                    delete_mode = True
            
            if delete_mode:
                requests.delete(f"https://api.notion.com/v1/blocks/{block['id']}", headers=headers)
                
    # 2. 새로운 진행률 블록 생성
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📊 실시간 진행률 (Progress)"}}]
            }
        },
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "전체 진행률: "},
                        "annotations": {"bold": True}
                    },
                    {
                        "type": "text",
                        "text": {"content": f"{generate_progress_bar(overall_pct, 20)}"}
                    }
                ],
                "icon": {"type": "emoji", "emoji": "🚀"},
                "color": "blue_background"
            }
        }
    ]
    
    # 스프린트별 바 추가
    for sprint_name, stats in sorted_sprints:
        total = stats["total"]
        comp = stats["completed"]
        pct = (comp / total * 100) if total > 0 else 0
        bar = generate_progress_bar(pct, 15)
        
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"🏃 {sprint_name}: "}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": f"{bar} ({comp}/{total})"}},
                ]
            }
        })
        
    payload = {"children": children}
    res = requests.patch(child_url, json=payload, headers=headers)
    if res.status_code == 200:
        print("Successfully updated dashboard progress bars.")
    else:
        print("Failed to update dashboard:", res.text)

if __name__ == "__main__":
    print("Calculating progress and updating Notion dashboard...")
    update_dashboard()
