from collections import OrderedDict
import dataclasses
import functools
import pprint
import re
from io import BytesIO
from typing import Required, TypedDict
from PIL import Image

from PIL.ImageFile import ImageFile
import hydrus_api
from pick import pick

from hydrustools.component.gui_util import flatList
from hydrustools.component.toolwindow import ToolWindow

from .settings import Settings

@dataclasses.dataclass
class TagInfo():
    count: int
    value: str


@dataclasses.dataclass(frozen=True)
class SiblingInfo():
    tag: str
    ideal_tag: str
    siblings: frozenset[str]
    ancestors: frozenset[str]
    descendants: frozenset[str]

class FileMetadata(TypedDict, total=False):
    file_id: Required[int]
    notes: Required[dict[str, str]]
    known_urls: Required[list[str]]
    tags: Required[dict[str, dict[str, dict[str, list[str]]]]]
    height: Required[int]
    width: Required[int]
    time_modified: Required[int]
    size: Required[int]
    is_deleted: Required[bool]
    is_inbox: Required[bool]
    is_local: Required[bool]
    is_trashed: Required[bool]
    hash: Required[str]



def set_api_key(new_api_key):
    Settings.hydrus_api_key = new_api_key


def get_api_credentials() -> tuple[str, str]:
    try:
        if not Settings.hydrus_api_key:
            raise AttributeError
    except AttributeError:
        Settings.hydrus_api_key = "CHANGEME"
        raise AttributeError("API key variable must be set! Edit ini file.")

    return (Settings.hydrus_api_key, Settings.hydrus_api_url)


client: hydrus_api.Client = None  # type: ignore
local_tags_service_key: str = None  # type: ignore
downloader_tags_service_key: str = None  # type: ignore


def init_client() -> None:
    global client
    global local_tags_service_key
    global downloader_tags_service_key

    api_key, api_url = get_api_credentials()
    client = hydrus_api.Client(api_key, api_url)

    tag_services = client.get_services()["local_tags"]
    local_tags_service = next(s for s in tag_services if s["name"] == "my tags")
    local_tags_service_key = local_tags_service["service_key"]

    downloader_tags_service = next(s for s in tag_services if s["name"] == "downloader tags")
    downloader_tags_service_key = downloader_tags_service["service_key"]


def chunk(iterable, maxsize):
    """A generator that yields lists of size `maxsize` containing the results of iterable `it`.

    Args:
        iterable: An iterable to split into chunks
        maxsize (int): Max size of chunks

    Yields:
        lists of size [1, maxsize]

    >>> list(chunk(range(10), 4))
    [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9)]
    """
    from itertools import islice

    iter_it = iter(iterable)
    yield from iter(lambda: tuple(islice(iter_it, maxsize)), ())


def search_tags_re(substr: str, subpattern: str | None, display_type="storage") -> list[TagInfo]:
    resp = client.search_tags(
        search=substr,
        tag_service_key=local_tags_service_key,
        tag_display_type=display_type
    )
    return [
        TagInfo(**item)
        for item in resp["tags"]  # type: ignore
        if (not subpattern) or re.match(subpattern, item["value"])
    ]


def replace_tag(original_tag: str, new_tags: list[str]) -> None:
    resp = client.search_files(tags=[original_tag])
    tagged_files = resp["file_ids"]
    # pprint.pprint(tagged_files)

    print(f"Replacing {original_tag!r} with {new_tags!r} in {len(tagged_files)} files")
    client.add_tags(
        file_ids=tagged_files,
        service_keys_to_actions_to_tags={
            local_tags_service_key: {
              hydrus_api.TagAction.ADD: new_tags,
              hydrus_api.TagAction.DELETE: [original_tag]
            }
        }
    )

def local_tags(metadata: FileMetadata, type_='display_tags') -> list[str]:
    return metadata['tags'][local_tags_service_key][type_].get(str(hydrus_api.TagStatus.CURRENT.value), [])

def get_sibling_ideal_targets(target_tags: list[str]) -> list[SiblingInfo]:
    resp = client.get_siblings_and_parents(target_tags)
    # pprint.pprint(resp)
    tags: dict[str, dict[str, str]] = resp["tags"]
    siblings: dict[str, SiblingInfo] = {
        k: SiblingInfo(
            tag=k,
            ideal_tag=v[local_tags_service_key]["ideal_tag"],  # type: ignore
            siblings=frozenset(v[local_tags_service_key]["siblings"]),  # type: ignore
            ancestors=frozenset(v[local_tags_service_key]["ancestors"]),  # type: ignore
            descendants=frozenset(v[local_tags_service_key]["descendants"]),  # type: ignore
        )
        # k: v[local_tags_service_key]
        for k, v in tags.items()
    }
    # pprint.pprint(siblings)
    targets: list[SiblingInfo] = [v for k, v in siblings.items()]
    return targets


def search_and_flatten_siblings(target_tags: list[str]) -> None:
    targets = get_sibling_ideal_targets(target_tags)
    # be kind,
    targets.sort(key=lambda si: si.tag)

    selected_indices = pick(
        [f'{si.tag} -> {si.ideal_tag}' for si in targets],
        "Tags to flatten",
        multiselect=True,
        min_selection_count=0
    )

    # Calculate real operations for approval
    selected_targets = [
        targets[index]
        for _, index in selected_indices  # type: ignore
    ]

    pprint.pprint(selected_targets)
    confirm = input("Confirm? (y/n): ").lower() == "y"

    if confirm:
        for si in selected_targets:
            replace_tag(si.tag, [si.ideal_tag])

@dataclasses.dataclass
class Namespace():
    name: str
    color: str = "#72a0c1"

namespace_list = [
    Namespace("series", "#aa00aa"),
    Namespace("character", "#00aa00"),
    Namespace("creator", "#aa0000"),
    Namespace("source", "#989898"),
]

namespace_map = OrderedDict((n.name, n) for n in namespace_list)

@functools.cache
def get_tag_namespace(tag: str) -> None | Namespace:
    if ":" not in tag:
        return None
    ns = tag.split(":")[0]
    return namespace_map.get(ns) or Namespace(ns)

@functools.cache
def get_tag_color(tag: str) -> None | str:
    namespace = get_tag_namespace(tag)
    if not namespace:
        return "#006ffa"
    return namespace.color

@functools.cache
def sort_tags_key(tag: str) -> tuple[int, ...]:
    namespace = get_tag_namespace(tag)
    ns_index = 99
    if namespace:
        ns_index = 100
        try:
            ns_index = namespace_list.index(namespace)
        except ValueError:
            pass
    return (
        ns_index,
    )

def sort_tags(tag_list: list[str]) -> list[str]:
    return sorted(tag_list, key=sort_tags_key)

def set_tag_list_of_images(tag_list: list[str], tool: ToolWindow, metadata_list: list[FileMetadata]):
    tool.setStatus(f"Setting {len(tag_list)} tags")
    file_ids = [m['file_id'] for m in metadata_list]

    client.add_tags(
        file_ids=file_ids,
        service_keys_to_tags={
            local_tags_service_key: tag_list,
        }
    )

    tool.logger.info(f"Checking differences: {[m['tags'] for m in metadata_list]=}")

    all_tags = set(flatList([
        local_tags(meta)
        for meta in metadata_list
    ]))

    tool.logger.info("%s, %s", all_tags, set(tag_list))

    removed_tags = set(all_tags).difference(set(tag_list))
    resp = client.get_siblings_and_parents(removed_tags)
    for k, v in resp["tags"].items():
        if v[local_tags_service_key]['ideal_tag'] in removed_tags:
            for s in v[local_tags_service_key]['siblings']:
                if s not in removed_tags:
                    tool.logger.warning(f"Also removing sibling tag {s}")
                    removed_tags.add(s)
    # We also need to remove any siblings of these tags


    if removed_tags:
        tool.logger.info(f"Removing tags: {removed_tags}")
        client.add_tags(
            file_ids=file_ids,
            service_keys_to_actions_to_tags={
                local_tags_service_key: {
                    hydrus_api.TagAction.DELETE: [*removed_tags]
                }
            }
        )

def get_render_scaled(file_id: int, width: int, height: int, max_width: int, max_height: int) -> ImageFile:
    ratio = min(max_width/width, max_height/height)
    resp = client.get_render(
        file_id=file_id,  # type: ignore
        height=int(ratio*height),
        width=int(ratio*width)
    )
    resp.raise_for_status()
    image = Image.open(BytesIO(resp.content))
    return image


def get_thumb_scaled(file_id: int, max_width: int, max_height: int) -> ImageFile:
    resp = client.get_thumbnail(file_id=file_id)
    resp.raise_for_status()
    image = Image.open(BytesIO(resp.content))
    # ratio =min(max_width/image.width, max_height/image.height)
    image.thumbnail((max_width, max_height))
    return image



def has_note(notename: str, max_n: int = 4) -> list[str]:
    return [
        *[f'system:has note with name "{notename}"'],
        *[f'system:has note with name "{notename} ({n})"' for n in range(1, max_n)]
    ]



if __name__ == "__main__":
    init_client()
