import dataclasses
import pprint
import re

import hydrus_api
from pick import pick

from .settings import HTSettings

Settings = HTSettings()


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


def search_tags_re(substr: str, subpattern: str, display_type="storage") -> list[TagInfo]:
    resp = client.search_tags(
        search=substr,
        tag_service_key=local_tags_service_key,
        tag_display_type=display_type
    )
    return [
        TagInfo(**item)
        for item in resp["tags"]  # type: ignore
        if re.match(subpattern, item["value"])
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


def get_sibling_ideal_targets(target_tags: list[str]) -> list[SiblingInfo]:
    resp = client.get_siblings_and_parents(target_tags)
    # pprint.pprint(resp)
    tags: dict[str, dict[str, str]] = resp["tags"]
    siblings: dict[str, SiblingInfo] = {
        k: SiblingInfo(
            tag=k,
            ideal_tag=v[local_tags_service_key]["ideal_tag"],
            siblings=frozenset(v[local_tags_service_key]["siblings"]),  # type: ignore
            ancestors=frozenset(v[local_tags_service_key]["ancestors"]),
            descendants=frozenset(v[local_tags_service_key]["descendants"])
        )
        # k: v[local_tags_service_key]
        for k, v in tags.items()
    }
    # pprint.pprint(siblings)
    targets: list[SiblingInfo] = [v for k, v in siblings.items() if k != v.ideal_tag]
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


if __name__ == "__main__":
    init_client()
