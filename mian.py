import os 
import asyncio
import aiohttp
import argparse
from syosetu import Syosetu, SyosuteArgs, SaveFormat

def parse_args() -> SyosuteArgs:
    parser = argparse.ArgumentParser(description="syosetu novel downloader")
    parser.add_argument("--novel_id", default="", help="Novel id", required=True)
    parser.add_argument("--save-format", default="txt", help="Save format, now support txt and epub(experimental), default is txt")
    parser.add_argument("--proxy", default="", help="Proxy")
    parser.add_argument("--output-dir", default="./downloads", help="Output directory")
    parser.add_argument("--record-chapter-number", default=False, help="Record Chapter Number, like [総第xxx話]")
    return parser.parse_args()


async def unittest():
    proxy = "http://localhost:10809"
    syosetu = Syosetu("n8920ex", proxy)
    await syosetu.async_init()
    await syosetu.async_download("epub", "./")
    await syosetu.async_close()
    from converters import convert_directory_txt_to_epub
    convert_directory_txt_to_epub("./", syosetu.novel_title)


async def main():
    args = parse_args()
    proxy = args.proxy
    novel_id = args.novel_id
    save_format = args.save_format

    syosetu = Syosetu(novel_id, proxy)
    await syosetu.async_init()
    syosetu.record_chapter_index = args.record_chapter_number

    await syosetu.async_download(args.output_dir)
    await syosetu.async_close()

    match save_format:
        case SaveFormat.TXT.value:
            pass
        case SaveFormat.EPUB.value:
            from converters import convert_directory_txt_to_epub
            convert_directory_txt_to_epub(os.path.join(args.output_dir, syosetu.novel_title))
        case _:
            print("Invalid save format")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (ConnectionResetError, aiohttp.ServerDisconnectedError, aiohttp.ClientConnectorError) as e:
        import traceback
        print(traceback.format_exc())
        print("check your network or proxy")