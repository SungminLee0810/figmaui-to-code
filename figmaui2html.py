import os
import requests
from dotenv import load_dotenv

# 환경 변수 로드 (.env 파일에 FIGMA_TOKEN, FIGMA_FILE_KEY 설정)
load_dotenv()
TOKEN = os.getenv("FIGMA_TOKEN")
FILE_KEY = os.getenv("FIGMA_FILE_KEY")
API_BASE = "https://api.figma.com/v1"
HEADERS = {"X-Figma-Token": TOKEN}


def get_file_node():
    """Figma 파일의 최상위 document 노드를 반환"""
    url = f"{API_BASE}/files/{FILE_KEY}"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return res.json()["document"]


def get_image_url(node_id):
    """특정 노드의 이미지를 추출하여 URL 반환"""
    url = f"{API_BASE}/images/{FILE_KEY}"
    params = {"ids": node_id, "format": "png", "scale": 1}
    res = requests.get(url, headers=HEADERS, params=params)
    res.raise_for_status()
    return res.json()["images"].get(node_id, "")


def rgba_from_fill(fill):
    """Fills 리스트 첫 번째 SOLID 타입 색상을 CSS rgba 문자열로 반환"""
    if fill.get("type") == "SOLID":
        c = fill["color"]
        r, g, b = int(c["r"] * 255), int(c["g"] * 255), int(c["b"] * 255)
        a = fill.get("opacity", 1)
        return f"rgba({r},{g},{b},{a})"
    return ""


def process_node(node):
    """
    단일 노드를 HTML 문자열로 변환 (재귀 처리 포함)
    텍스트 노드는 background-color를 적용하지 않음.
    """
    css = ""
    html = ""
    t = node.get("type")

    # 1) 절대 위치 & 크기
    if "absoluteBoundingBox" in node:
        bb = node["absoluteBoundingBox"]
        css += (
            f"position:absolute; "
            f"left:{bb['x']}px; top:{bb['y']}px; "
            f"width:{bb['width']}px; height:{bb['height']}px; "
        )

    # 2) Auto Layout → Flexbox
    if node.get("layoutMode"):
        mode = node["layoutMode"]
        css += "display:flex; "
        css += f"flex-direction:{'row' if mode=='HORIZONTAL' else 'column'}; "
        css += f"gap:{node.get('itemSpacing', 0)}px; "
        css += (
            f"padding:{node.get('paddingTop',0)}px "
            f"{node.get('paddingRight',0)}px "
            f"{node.get('paddingBottom',0)}px "
            f"{node.get('paddingLeft',0)}px; "
        )
        css += f"align-items:{node.get('primaryAxisAlignItems','MIN').lower()}; "
        css += f"justify-content:{node.get('counterAxisAlignItems','MIN').lower()}; "

    # 3) Constraints → CSS 크기/정렬
    cons = node.get("constraints", {})
    h = cons.get("horizontal")
    if h == "STRETCH":
        css += "width:100%; "
    elif h == "CENTER":
        css += "margin-left:auto; margin-right:auto; "
    v = cons.get("vertical")
    if v == "STRETCH":
        css += "height:100%; "
    elif v == "CENTER":
        css += "margin-top:auto; margin-bottom:auto; "

    # 4) Layout Grid → CSS Grid
    grids = node.get("layoutGrids", [])
    if grids:
        g = grids[0]
        if g.get("pattern") == "COLUMNS":
            css += "display:grid; "
            css += f"grid-template-columns: repeat({g.get('count')}, 1fr); "
            css += f"column-gap: {g.get('gutterSize',0)}px; "

    # 5) 배경색 (fills) — TEXT 타입이 아닌 경우에만 적용
    if t != "TEXT":
        fills = node.get("fills") or []
        if fills:
            color_str = rgba_from_fill(fills[0])
            if color_str:
                css += f"background-color: {color_str}; "

    # 6) 타입별 HTML 생성
    if t == "TEXT":
        # 오직 font-size 및 텍스트 색상만 지정, 배경색 제거
        style = node.get("style", {})
        size = style.get("fontSize", 12)
        # 텍스트 색상만 적용
        text_color = "black"
        fills = node.get("fills") or []
        if fills and fills[0].get("type") == "SOLID":
            text_color = rgba_from_fill(fills[0])
        html = (
            f"<p style=\"{css}font-size:{size}px; color:{text_color};\">"
            f"{node.get('characters','')}</p>"
        )
    elif t == "IMAGE":
        src = get_image_url(node["id"])
        html = f"<img src=\"{src}\" style=\"{css}\" />"
    else:
        html = f"<div style=\"{css}\"></div>"

    # 자식 노드 재귀 처리
    for child in node.get("children", []):
        html += process_node(child)

    return html


def generate_html(doc_node):
    """전체 문서를 HTML로 생성하여 파일로 저장"""
    body_html = process_node(doc_node)
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Figma to HTML</title>
  <style>body{{position:relative;margin:0;padding:0;}}</style>
</head>
<body>
{body_html}
</body>
</html>"""
    with open("output.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("✅ output.html 생성 완료")


if __name__ == "__main__":
    doc = get_file_node()
    generate_html(doc)