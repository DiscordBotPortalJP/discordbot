import asyncio
import aiohttp

async def create_notion_page_async(token, database_id, page_title, page_content):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2021-05-13"  # Notion APIのバージョンを指定
    }

    page_properties = {
        "title": [
            {
                "text": {
                    "content": page_title
                }
            }
        ],
        "rich_text": [
            {
                "text": {
                    "content": page_content
                }
            }
        ]
    }

    data = {
        "parent": {
            "database_id": database_id
        },
        "properties": page_properties
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                print(f"Page '{page_title}' created successfully in Notion!")
            else:
                print(f"Failed to create page in Notion. Status code: {response.status}")

# 以下は実行例です
notion_token = "YOUR_NOTION_TOKEN"  # 自身のNotion Integrationのトークンを入力してください
notion_database_id = "YOUR_NOTION_DATABASE_ID"  # ページを作成したいNotionデータベースのIDを入力してください
page_title = "New Page Title"
page_content = "This is the content of the new page. You can add more lines as needed."

# 非同期処理を実行するために、イベントループを作成して関数を実行します
loop = asyncio.get_event_loop()
loop.run_until_complete(create_notion_page_async(notion_token, notion_database_id, page_title, page_content))
