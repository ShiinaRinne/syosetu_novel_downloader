import os
import shutil
import aiohttp
import asyncio
import aiofiles
import argparse
from typing import Dict
from pydantic import BaseModel
from bs4 import BeautifulSoup, Tag

MAIN_URL = "https://ncode.syosetu.com"
NOVEL_ID = ""
SILENT = False
PROXY = ""

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
}


async def fetch_novel_info(session: aiohttp.ClientSession) -> str:
    async with session.get(f"{MAIN_URL}/{NOVEL_ID}", headers=headers, proxy=PROXY) as response:
        return await response.text()


async def fetch_chapters_info(session: aiohttp.ClientSession, chapter: int) -> str:
    async with session.get(f"{MAIN_URL}/{NOVEL_ID}/{chapter}", headers=headers, proxy=PROXY) as response:
        return await response.text()


async def fetch_novel_parts(session: aiohttp.ClientSession) -> Dict[str, range]:
    html = await fetch_novel_info(session)

    parts = {}
    start = 1
    current_title = None
    count = 0

    soup = BeautifulSoup(html, "html.parser")
    for element in soup.find_all(['div', 'dl'], class_=['chapter_title', 'novel_sublist2']):
        element: Tag
        if element['class'][0] == 'chapter_title':
            if current_title is not None:
                parts[current_title] = range(start, start + count)
            current_title = element.get_text(strip=True)
            start += count
            count = 0
        elif element['class'][0] == 'novel_sublist2':
            count += 1

    if current_title is not None:
        parts[current_title] = range(start, start + count)

    return parts


async def fetch_novel_parts2(session: aiohttp.ClientSession) -> Dict[str, range]:
    """
    structure:

    chapter:Dict[str,range] = {
        "第一部　断頭台の姫君":range(1,148),
        "第二部　導(しるべ)の少女":range(148,266),
        "第三部　月と星々の新たなる盟約":range(266,376),
        "第四部　その月の導く明日へ":range(376,619),
        "第五部　皇女の休日":range(619, 696),
        "第六部　馬夏(まなつ)の青星夜(よ)の満月夢(ゆめ)":range(696, 808),
        "第七部　輝け！　黄金の海月の灯台":range(808, 940),
        "第八部　第二次司教帝選挙～女神肖像画の謎を追え！～":range(940, 1098),
    }
    """

    html = await fetch_novel_info(session)
    soup = BeautifulSoup(html, "html.parser")
    chapters = {}
    chapter_titles: Tag = soup.find_all('div', class_='chapter_title')
    for title in chapter_titles:
        chapter_title: Tag = title.get_text(strip=True)
        chapter_numbers = []
        next_element = title.find_next_sibling()
        while next_element and next_element.name != 'div':
            if next_element.name == 'dl' and 'novel_sublist2' in next_element.get('class', []):
                a_tag = next_element.find('a', href=True)
                if a_tag:
                    chapter_number = int(a_tag['href'].split('/')[-2])
                    chapter_numbers.append(chapter_number)
            next_element = next_element.find_next_sibling()

        if chapter_numbers:
            chapters[chapter_title] = range(min(chapter_numbers), max(chapter_numbers) + 1)
    return chapters


async def get_chapters(session: aiohttp.ClientSession) -> range:
    html = await fetch_novel_info(session)
    soup = BeautifulSoup(html, "html.parser")
    chapters = soup.find_all("dd")
    return range(1, len(chapters) + 1)


async def get_title_content(session: aiohttp.ClientSession, chapter: int) -> (str, str):
    html = await fetch_chapters_info(session, chapter)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("p", class_="novel_subtitle").text.replace("\u3000", " ")
    content = soup.find("div", id="novel_honbun").text.replace("\u3000", "")
    return title, content


async def get_novel_title(session: aiohttp.ClientSession) -> str:
    html = await fetch_novel_info(session)
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("p", class_="novel_title").text


class SyosuteArgs(BaseModel):
    novel_id: str
    proxy: str = ""
    silent: bool = False


def print_log(*args, **kwargs):
    if not SILENT:
        print(*args, **kwargs)


def parse_args() -> SyosuteArgs:
    parser = argparse.ArgumentParser(description="syosetu novel downloader")
    parser.add_argument("--novel_id", default="", help="Novel id.", required=True)
    parser.add_argument("--proxy", default="", help="Proxy")
    parser.add_argument("--silent", default=False, help="Silent mode")
    return parser.parse_args()


async def main():
    global PROXY, SILENT, NOVEL_ID
    args = parse_args()
    PROXY = args.proxy
    SILENT = args.silent
    NOVEL_ID = args.novel_id

    async with aiohttp.ClientSession() as session:
        novel_title = await get_novel_title(session)
        if os.path.exists(novel_title): shutil.rmtree(novel_title)
        os.mkdir(novel_title)
        os.chdir(novel_title)

        print_log(f"novel_title: {novel_title}")


        parts: Dict[str, range] = await fetch_novel_parts2(session)
        print_log((len(parts) == 0) and "No part\n" or f"All parts:\n{"\n".join(list(parts.keys()))}\n")

        if (len(parts) != 0):
            for k, v in parts.items():
                print_log(f"Start download part: {k}")
                async with aiofiles.open(f"{k}.txt", "w", encoding="utf-8") as f:
                    for chapter_index in v:
                        title, content = await get_title_content(session, chapter_index)
                        await f.write(f"● {title} [総第{chapter_index}話]\n")
                        await f.write(f"{content}\n")
                        print_log(f"    {title} success")
        else:
            async with aiofiles.open(f"{novel_title}.txt", "w", encoding="utf-8") as f:
                print_log(f"Start download novel: {novel_title}")
                for chapter_index in await get_chapters(session):
                    title, content = await get_title_content(session, chapter_index)
                    await f.write(f"● {title} [総第{chapter_index}話]\n")
                    await f.write(f"{content}\n")
                    print_log(f"    {title} success")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except aiohttp.ClientConnectionError:
        print("Timeout, please try again or check your proxy")
    except Exception as e:
        print(e.__traceback__)
