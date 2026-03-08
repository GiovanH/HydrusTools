import concurrent.futures
import functools
import tkinter as tk
from PIL import Image, ImageDraw, ImageFile, ImageTk
import logging

from collections import UserDict, OrderedDict
from typing import Mapping, TypeVar, Generic

K = TypeVar('K')
V = TypeVar('V')

from hydrustools import htlogging, logic
from hydrustools.util import timer

ImageFile.LOAD_TRUNCATED_IMAGES = True


logger = logging.getLogger(__name__)

@functools.cache
def render_image(file_id: int, width: int, height: int, max_width: int, max_height: int) -> Image.Image:
    if max_height <= 1 or max_width <= 1:
        raise ValueError(f"Invalid dimensions {width=} {height=} {max_width=} {max_height=}")
    with timer(f"Render {file_id} {width=} {height=} {max_width=} {max_height=}"):
        try:
            return logic.get_render_scaled(file_id, width, height, max_width, max_height)
        except:  # noqa: E722
            return logic.get_thumb_scaled(
                file_id,  # type: ignore
                max_width=max_width,
                max_height=max_height
            )

class LRUDict(UserDict[K, V], Generic[K, V]):
    def __init__(self, max_items: int):
        super().__init__()
        self.max_items = max_items
        self.data: OrderedDict[K, V] = OrderedDict() # type: ignore

    def __getitem__(self, key: K) -> V:
        value = self.data.pop(key)
        self.data[key] = value  # Move to end (most recently used)
        return value

    def __setitem__(self, key: K, value: V) -> None:
        if key in self.data:
            self.data.pop(key)
        elif len(self.data) >= self.max_items:
            self.data.popitem(last=False)  # Remove least recently used
        self.data[key] = value

    def __delitem__(self, key: K) -> None:
        self.data.pop(key)

class ContentCanvas(tk.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)

        self.current_photoimg: ImageTk.PhotoImage | None = None
        self.current_meta: logic.FileMetadata | None = None

        self.photoimage_cache: UserDict[tuple, ImageTk.PhotoImage] = LRUDict(30)

        self.initwindow()

    def destroy(self):
        self.thread_pool.shutdown(wait=False, cancel_futures=True)
        super().destroy()

    def initwindow(self) -> None:
        # set first image on canvas, an ImageTk.PhotoImage
        self.photoimage = self.create_image(0, 0, anchor="nw")

        self.bind("<Configure>", lambda e: self.after(100, self.configure_image))

    def set_image(self, image: logic.FileMetadata):
        self.current_meta = image
        try:
            self.configure_image()
        except ValueError:
            # Window not configured
            pass

    def configure_image(self, event=None):
        if not self.current_meta:
            return
        imagefile = render_image(
            self.current_meta['file_id'],
            self.current_meta['width'], self.current_meta['height'],
            self.winfo_width(), self.winfo_height()
        )
        with timer(f"Configure {self.current_meta['file_id']}"):
            key = (self.current_meta['file_id'], self.winfo_width(), self.winfo_height())

            self.current_photoimg = self.photoimage_cache.get(key) or ImageTk.PhotoImage(image=imagefile)
            self.itemconfig(self.photoimage, image=self.current_photoimg, state="normal")
            self.photoimage_cache[key] = self.current_photoimg

    def preload_image(self, image: logic.FileMetadata):
        self.thread_pool.submit(
            render_image,
            image['file_id'],
            image['width'], image['height'],
            self.winfo_width(), self.winfo_height()
        )

    def placeholderImage(self) -> Image.Image:
        pilimg = Image.new('RGB', (10, 10), color=(0, 0, 0))
        ImageDraw.Draw(pilimg).text((2, 0), "?", fill=(255, 255, 255))
        return pilimg
