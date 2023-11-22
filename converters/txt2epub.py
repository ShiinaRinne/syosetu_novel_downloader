from ebooklib import epub
import re
import os

def create_epub_from_txt(file_path, output_folder):
    print(f"convert {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        text_content = file.read()

    chapters = re.split(r'● ', text_content)

    book = epub.EpubBook()

    book.set_identifier('id' + str(os.path.basename(file_path)))
    title = os.path.basename(file_path).split(".")[:-1][0]
    book.set_title(title)
    book.set_language('ja')

    book.spine = ['nav']

    for i, chapter in enumerate(chapters):
        if not chapter.strip():
            continue

        c = epub.EpubHtml(title=f"{chapter.split('\n', 1)[0]}", file_name=f'chap_{i+1}.xhtml', lang='ja')
        c.content = '<h1>' + chapter.split('\n', 1)[0] + '</h1>' + chapter.split('\n', 1)[1]

        book.add_item(c)

        book.spine.append(c)

    book.toc = tuple(book.spine[1:])
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(os.path.join(output_folder, f'{title}.epub'), book, {})

def convert_directory_txt_to_epub(*args):
    dir = os.path.join(*args)
    for file in os.listdir(dir):
        if file.endswith(".txt"):
            create_epub_from_txt(os.path.join(dir, file), dir)