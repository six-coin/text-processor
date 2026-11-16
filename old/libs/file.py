import os
import shutil


def make_dir(path):
    os.makedirs(os.path.abspath(path), exist_ok=True)


def new_file(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


def add_file(path, content):
    if not exists(path) or not is_file(path):
        new_file(path)
    with open(path, "a", encoding="utf-8") as file:
        file.write(content)


def read_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def list_dir(path):
    return os.listdir(path)


def move(origin, destination):
    shutil.move(origin, destination)


def is_dir(path):
    return os.path.isdir(path)


def is_file(path):
    return os.path.isfile(path)


def exists(path):
    return os.path.exists(path)


def delete(path):
    os.remove(os.path.abspath(path))


def open_file(path):
    if os.path.isfile(path):
        os.startfile(os.path.abspath(path))


def open_dir(path):
    if os.path.isdir(path):
        os.startfile(os.path.abspath(path))
