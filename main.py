#  import argparse
import traceback
import os
from pathlib import Path

from src.menu import Ranobe2ebook
from src.fb2 import FB2Handler
from src.epub import EpubHandler

if __name__ == "__main__":
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--test", type=str, default=None)
    # args = parser.parse_args()

    # if args.test:
    #     print("Запущен скрипт с включенной детализацией")

    doc_path = os.path.normpath(os.path.expanduser("~/Documents"))
    logs_dir = f"{doc_path}\\ranobelib-parser-logs"
    Path(f"{logs_dir}").mkdir(parents=True, exist_ok=True)
    try:
        app = Ranobe2ebook(handlers={"fb2": FB2Handler, "epub": EpubHandler})
        app.run()
    except RuntimeError:
        pass
    except Exception:
        full_path = f"{logs_dir}\\traceback.txt"

        print("Произошла непредвиденная ошибка.\nПодробности в файле: " + full_path)
        print("\n" + ("-" * 60) + "\n", file=open(full_path, "a"))
        traceback.print_exc(file=open(full_path, "a"))
    input("Нажмите Enter для выхода...")
