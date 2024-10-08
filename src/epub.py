import time
from typing import Callable


from bs4 import BeautifulSoup
from ebooklib import epub
import requests

from src.model import ChapterData, ChapterMeta, Handler, Image
from src.api import get_chapter, get_image_content


class EpubHandler(Handler):
    book: epub.EpubBook
    log_func: Callable
    progress_bar_step: Callable
    min_volume: str
    max_volume: str

    def _parse_html(self, chapter: ChapterData) -> tuple[list[str], dict[str, Image]]:
        try:
            soup = BeautifulSoup(chapter.content, "html.parser")
            tags: list = []
            images: dict[str, Image] = {}
            for tag in soup.find_all(recursive=False):
                if tag.name == "img":
                    url = tag["src"]
                    img_filename = url.split("/")[-1]
                    img_uid = f"{chapter.id}_{img_filename}"
                    image = Image(
                        uid=img_uid,
                        name=img_filename.split(".")[0],
                        url=url,
                        extension=img_filename.split(".")[-1],
                    )
                    images[image.name] = image
                    tag["src"] = image.static_url

                tags.append(tag)
        except Exception as e:
            self.log_func(e)

        return tags, images

    def _parse_doc(self, chapter: ChapterData) -> tuple[list[str], dict[str, Image]]:
        attachments = chapter.attachments
        img_base_url = "https://ranobelib.me"
        images: dict[str, Image] = {}
        tags: list[str] = []

        for attachment in attachments:
            img_uid = f"{chapter.id}_{attachment.filename}"
            images[attachment.name] = Image(
                uid=img_uid,
                name=attachment.name,
                url=img_base_url + attachment.url,
                extension=attachment.extension,
            )

        for item in chapter.content:
            if item.get("type") == "image":
                img_name = item.get("attrs").get("images")[-1].get("image")
                tags.append(f"<img src='static/{images.get(img_name).uid}'/>")

            elif item.get("type") == "paragraph":
                text = ""
                paragraph_content = item.get("content")
                if paragraph_content and paragraph_content[0].get("type") == "text":
                    text = paragraph_content[0].get("text")

                tags.append(f"<p>{text}</p>")

            elif item.get("type") == "horizontalRule":
                tags.append("<hr/>")

        return tags, images

    def _make_chapter(
        self, slug: str, priority_branch: str, item: ChapterMeta
    ) -> tuple[epub.EpubHtml, dict[str, Image]]:
        try:
            chapter: ChapterData = get_chapter(
                slug,
                priority_branch,
                item.number,
                item.volume,
            )
        except Exception as e:
            self.log_func(str(e))
            return None, None

        chapter_title = f"Том {item.volume}. Глава {item.number}. {item.name}"

        epub_chapter = epub.EpubHtml(
            title=chapter_title,
            file_name=item.number + "_" + item.volume + ".xhtml",
        )
        tags, images = [], {}

        if chapter.type == "html":
            tags, images = self._parse_html(chapter)
            epub_chapter.set_content(f"<h1>{chapter_title}</h1>" + "".join([tag.__str__() for tag in tags]))

        elif chapter.type == "doc":
            tags, images = self._parse_doc(chapter)
            epub_chapter.set_content(
                f"<h1>{chapter_title}</h1>" + "".join([tag for tag in tags]),
            )
        else:
            self.log_func("Неизвестный тип главы! Невозможно преобразовать в EPUB!")
            return None, None

        return epub_chapter, images

    def save_book(self, dir: str) -> None:
        safe_title = self.book.title.replace(":", "")
        epub.write_epub(f"{dir}\\{safe_title}.epub", self.book)
        self.log_func(f"Книга {self.book.title} сохранена в формате Epub.")
        self.log_func(f"В каталоге {dir} создана книга {safe_title}.epub.")

    def end_book(self) -> None:
        self.book.toc = (epub.Section("1"),) + tuple(
            chap for chap in self.book.items if isinstance(chap, epub.EpubHtml)
        )

        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())
        self.book.spine = ["nav"] + [chap for chap in self.book.items if isinstance(chap, epub.EpubHtml)]

        self.book.add_metadata(
            None,
            "meta",
            "",
            {"name": "series_index", "content": f"Тома c {self.min_volume} по {self.max_volume}"},
        )

    def fill_book(
        self,
        name: str,
        priority_branch: str,
        chapters_data: list[ChapterMeta],
        worker,
        delay: float = 0.5,
    ) -> None:
        self.min_volume = str(chapters_data[0].volume)
        self.max_volume = str(chapters_data[-1].volume)

        total_len = len(str(len(chapters_data)))
        chap_len = len(str(max(chapters_data, key=lambda x: len(str(x.number))).number))
        volume_len = len(self.max_volume)

        self.log_func(f"\nНачинаем скачивать главы: {len(chapters_data)}")

        for i, item in enumerate(chapters_data, 1):
            time.sleep(delay)
            if worker.is_cancelled:
                break

            epub_chapter, images = self._make_chapter(name, priority_branch, item)
            if epub_chapter is None:
                self.log_func("Пропускаем главу.")
                continue

            self.book.add_item(epub_chapter)
            for img in images.values():
                try:
                    self.book.add_item(
                        epub.EpubImage(
                            uid=img.name,
                            file_name=img.static_url,
                            media_type=img.media_type,
                            content=get_image_content(img.url, img.extension),
                        )
                    )
                except Exception as e:
                    self.log_func(str(e))
                    continue

            self.log_func(
                f"Скачали {i:>{total_len}}: Том {item.volume:>{volume_len}}. Глава {item.number:>{chap_len}}. {item.name}"
            )

            self.progress_bar_step(1)

    def make_book(self, ranobe_data: dict) -> None:
        self.log_func("\nПодготавливаем книгу...")

        title = ranobe_data.get("rus_name") if ranobe_data.get("rus_name") else ranobe_data.get("name")

        book: epub.EpubBook = epub.EpubBook()
        book.set_title(title)

        book.set_language("ru")
        for author in ranobe_data.get("authors"):
            book.add_author(author.get("name"))

        cover_url = ranobe_data.get("cover").get("default")
        book.set_cover(cover_url.split("/")[-1], requests.get(cover_url).content, False)

        book.add_metadata(
            "DC",
            "subject",
            " ".join([genre.get("name") for genre in ranobe_data.get("genres")]),
        )
        book.add_metadata("DC", "description", ranobe_data.get("summary").replace("\n", "<p>"))
        book.add_metadata("DC", "contributor", "RanobeLIB 2 ebook")
        book.add_metadata("DC", "source", "ranobelib.me")
        book.add_metadata(
            None,
            "meta",
            "",
            {
                "name": "series",
                "content": ranobe_data.get("franchise")[0].get("name")
                if ranobe_data.get("franchise")
                else ranobe_data.get("name"),
            },
        )

        self.log_func("Подготовили книгу.")

        self.book = book
