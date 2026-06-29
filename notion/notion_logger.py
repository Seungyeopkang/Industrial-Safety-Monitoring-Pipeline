import os
import sys
import re
import argparse
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_API_KEY or NOTION_API_KEY == "your_notion_api_key_here":
    print("Error: NOTION_API_KEY가 .env 파일에 올바르게 설정되지 않았습니다.")
    sys.exit(1)

if not NOTION_DATABASE_ID or NOTION_DATABASE_ID == "your_notion_database_id_here":
    print("Error: NOTION_DATABASE_ID가 .env 파일에 올바르게 설정되지 않았습니다.")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def parse_inline_text(text):
    """
    텍스트 내의 **굵게**, `코드`, [링크](URL) 마크다운 문법을 파싱하여
    노션 rich_text 포맷으로 변환합니다.
    """
    pattern = re.compile(
        r'(\*\*(?P<bold>[^\*]+)\*\*)|'
        r'(`(?P<code>[^`]+)`)|'
        r'(\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^\)]+)\))'
    )
    
    rich_text = []
    last_idx = 0
    
    for match in pattern.finditer(text):
        if match.start() > last_idx:
            plain_part = text[last_idx:match.start()]
            rich_text.append({
                "type": "text",
                "text": {"content": plain_part}
            })
            
        gd = match.groupdict()
        if gd.get("bold"):
            rich_text.append({
                "type": "text",
                "text": {"content": gd["bold"]},
                "annotations": {"bold": True}
            })
        elif gd.get("code"):
            rich_text.append({
                "type": "text",
                "text": {"content": gd["code"]},
                "annotations": {"code": True}
            })
        elif gd.get("link_text"):
            rich_text.append({
                "type": "text",
                "text": {
                    "content": gd["link_text"],
                    "link": {"url": gd["link_url"]}
                }
            })
            
        last_idx = match.end()
        
    if last_idx < len(text):
        rich_text.append({
            "type": "text",
            "text": {"content": text[last_idx:]}
        })
        
    return rich_text

def convert_markdown_to_blocks(markdown_text):
    """
    마크다운 텍스트를 노션 블록 객체 배열로 변환합니다.
    """
    blocks = []
    lines = markdown_text.split('\n')
    
    in_code_block = False
    code_content = []
    code_language = "plain text"
    
    for line in lines:
        stripped = line.strip()
        
        # 코드 블록 처리
        if stripped.startswith("```"):
            if in_code_block:
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": "\n".join(code_content)}}],
                        "language": code_language
                    }
                })
                code_content = []
                in_code_block = False
            else:
                in_code_block = True
                lang = stripped[3:].strip()
                code_language = lang if lang else "plain text"
            continue
            
        if in_code_block:
            code_content.append(line)
            continue
            
        if not stripped:
            continue
            
        # Headings
        if stripped.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": parse_inline_text(stripped[4:])
                }
            })
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": parse_inline_text(stripped[3:])
                }
            })
        elif stripped.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": parse_inline_text(stripped[2:])
                }
            })
        # Blockquotes
        elif stripped.startswith("> "):
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": parse_inline_text(stripped[2:])
                }
            })
        # Bullet Lists
        elif stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("· ") or stripped.startswith("• "):
            content = stripped[2:]
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": parse_inline_text(content)
                }
            })
        # Regular Paragraph
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": parse_inline_text(line)
                }
            })
            
    return blocks

def create_dev_log(title, content_markdown, sprint=None, categories=None):
    url = "https://api.notion.com/v1/pages"
    
    blocks = convert_markdown_to_blocks(content_markdown)
    
    # 기본 properties 설정 (이름)
    properties = {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": title
                    }
                }
            ]
        }
    }
    
    # 1. 제목에서 날짜 추출 (YYYY-MM-DD)
    date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', title)
    if date_match:
        extracted_date = date_match.group(1)
        properties["Date"] = {
            "date": {
                "start": extracted_date
            }
        }
        
    # 2. 스프린트 속성 추가
    if sprint:
        properties["Sprint"] = {
            "select": {
                "name": sprint
            }
        }
        
    # 3. 카테고리 속성 추가
    if categories:
        category_list = [c.strip() for c in categories.split(",") if c.strip()]
        properties["Category"] = {
            "multi_select": [{"name": c} for c in category_list]
        }
        
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
        "children": blocks
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        print(f"성공: 노션에 '{title}' 페이지를 성공적으로 생성했습니다!")
        return True
    else:
        print(f"실패 (상태 코드: {response.status_code})")
        print("응답 메시지:", response.text)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="노션 개발 일지 자동 생성 스크립트")
    parser.add_argument("title", type=str, help="일지 제목 (형식: YYYY-MM-DD | 제목)")
    parser.add_argument("content", type=str, help="일지 마크다운 내용")
    parser.add_argument("--sprint", type=str, choices=["Sprint 1", "Sprint 2", "Sprint 3", "Sprint 4"], help="해당 스프린트")
    parser.add_argument("--categories", type=str, help="카테고리 목록 (쉼표로 구분, 예: '환경 구성,디버깅')")
    
    args = parser.parse_args()
    
    create_dev_log(args.title, args.content, args.sprint, args.categories)
