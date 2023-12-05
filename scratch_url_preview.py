import requests
from bs4 import BeautifulSoup

def get_preview(url):
    # 發送 HTTP 請求並取得 HTML 內容
    response = requests.get(url)
    html_content = response.text
    # 指定要查找的 properties
    properties = ['og:image', 'og:title','og:description']
    attrs = ['link_image','link_title','link_description']
    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    link_contents = {}
    for attr, property in zip(attrs, properties):
        temp = soup.find('meta', {'property': property})
        if temp is not None:
            link_contents[attr] = temp.get('content')
        else:
            try:
                temp = soup.find('meta', {'name': property[3:]})
                if temp is not None:
                    link_contents[attr] = temp.get('content')
                else:
                    print(temp)
                    print(f"{attr} not found")
            except Exception as e:
                print(f"Error: {e}")
    return link_contents