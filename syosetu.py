import os
import shutil
import ssl
import aiohttp
import aiofiles
from bs4 import BeautifulSoup, Tag # type: ignore
from pydantic import BaseModel
from enum import Enum
from asyncio import Semaphore
from deprecated import deprecated

from custom_typing import NovelTitle, ChapterContent, ChapterRange, PartTitle, ChapterTitle


MAIN_URL: str = "https://ncode.syosetu.com"

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
}


class Syosetu:
    def __init__(self, novel_id:str, proxy:str = "") -> None:
        self.novel_id = novel_id
        self.proxy = proxy
        self.novel_title: NovelTitle = ""

        self.record_chapter_index = False

        self.__semaphore = Semaphore(8)


    async def async_init(self):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.__session: aiohttp.ClientSession = aiohttp.ClientSession(connector=connector)
        self.__novel_info_soup = await self.__fetch_novel_info()
        self.novel_title = self.__get_novel_title()
        self.author = self.__get_novel_author()


    async def async_close(self):
        if self.__session:
            await self.__session.close()
            self.__session = None


    async def __fetch_novel_info(self) -> BeautifulSoup:
        async with self.__session.get(f"{MAIN_URL}/{self.novel_id}", headers=headers, proxy=self.proxy) as response:
            return BeautifulSoup(await response.text(), "html.parser")
        
    
    async def __fetch_chapters_info(self, chapter: int) -> BeautifulSoup:
        async with self.__session.get(f"{MAIN_URL}/{self.novel_id}/{chapter}", headers=headers, proxy=self.proxy) as response:
            return BeautifulSoup(await response.text(), "html.parser")
        
    
    async def __get_novel_parts(self) -> dict[NovelTitle, ChapterRange]:
        """
        structure:

        chapter:dict[str,range] = {
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

        chapters = {}
        chapter_titles: Tag = self.__novel_info_soup.find_all('div', class_='p-eplist__chapter-title')
        for title in chapter_titles:
            chapter_title: Tag = title.get_text(strip=True)
            chapter_numbers = []
            next_element = title.find_next_sibling()
            while next_element and next_element.name == 'div' and 'p-eplist__sublist' in next_element.get('class', []):
                a_tag = next_element.find('a', href=True)
                if a_tag:
                    chapter_number = int(a_tag['href'].split('/')[-2])
                    chapter_numbers.append(chapter_number)
                next_element = next_element.find_next_sibling()

            if chapter_numbers:
                chapters[chapter_title] = range(min(chapter_numbers), max(chapter_numbers) + 1)
        return chapters
    

    @deprecated(version='0.1.0', reason="Feeling bad, so use __get_novel_parts instead")
    async def __get_novel_parts2(self) -> dict[NovelTitle, ChapterRange]:
        parts = {}
        start = 1
        current_title = None
        count = 0

        for element in self.__novel_info_soup.find_all(['div', 'dl'], class_=['chapter_title', 'novel_sublist2']):
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


    def __get_novel_title(self) -> NovelTitle:
        return self.__novel_info_soup.find("h1", class_="p-novel__title").text


    def __get_novel_author(self)-> str:
        return self.__novel_info_soup.find("a", href=True).text 


    def __get_chapters_range(self) -> ChapterRange:
        chapters = self.__novel_info_soup.find_all("dd")
        return range(1, len(chapters) + 1)


    async def __get_chapter_title_content(self, chapter: int) -> tuple[ChapterTitle, ChapterContent]:
        soup:BeautifulSoup = await self.__fetch_chapters_info(chapter)
        title = soup.find("h1", class_="p-novel__title").text.replace("\u3000", " ")
        content = soup.find("div", class_="p-novel__body").text.replace("\u3000", "")
        return title, content
    

    async def __async_save_txt(self, title: ChapterTitle | PartTitle, content: ChapterContent, chapter_index, file_path:str) -> None:
        async with aiofiles.open(f"{file_path}.txt", "a+", encoding="utf-8") as f:
            if self.record_chapter_index:
                await f.write(f"● {title} [総第{chapter_index}話]\n")
            else: 
                await f.write(f"● {title}\n")

            await f.write(f"{content}\n")


    # TODO: add cover, 
    async def async_save(self, chapter_index:int, file_path) -> None:
        async with self.__semaphore:
            title, content = await self.__get_chapter_title_content(chapter_index)
            await self.__async_save_txt(title, content, chapter_index, file_path)
            print(f"    {title} save success")


    async def async_download(self, output_dir)->None:
        output_dir = os.path.join(output_dir, self.novel_title)
        print(output_dir)
        if os.path.exists(output_dir): 
            shutil.rmtree(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        parts: dict[PartTitle, ChapterRange] = await self.__get_novel_parts()
        print((len(parts) == 0) and "No part\n" or f"All parts:\n{"\n".join(list(parts.keys()))}\n")

        if(len(parts)!=0): # novel has parts
            for k, v in parts.items():
                print(f"Start download part: {k}")

                # legacy
                for chapter_index in v:
                    await self.async_save(chapter_index, os.path.join(output_dir,  k))

                # gather expermital
                # await asyncio.gather(*(self.async_save(chapter_index, os.path.join(output_dir, k)) for chapter_index in v))

                # gather 2
                # async with self.__semaphore:
                #     results = await asyncio.gather(*(self.__fetch_chapters_info(chapter_index) for chapter_index in v))
                # chapters_content = OrderedDict()
                # for chapter_index, content in zip(v, results):
                #     chapters_content[chapter_index] = content

                # for chapter_index, content in chapters_content.items():
                #     await self.__async_save_txt(chapter_index, output_dir)

        else: # novel has no parts
            print(f"Start download novel: {self.novel_title}")
            for chapter_index in self.__get_chapters_range():
                await self.async_save(chapter_index, os.path.join(output_dir, self.novel_title))
            # gather expermital
            # await asyncio.gather(*(self.async_save(chapter_index, os.path.join(output_dir, self.novel_title)) for chapter_index in self.__get_chapters_range()))
    

class SaveFormat(Enum):
    TXT  = "txt"
    EPUB = "epub"


class SyosuteArgs(BaseModel):
    novel_id: str
    proxy: str
    output_dir: str
    save_format: SaveFormat
    record_chapter_number: bool

