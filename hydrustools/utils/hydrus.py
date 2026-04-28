from collections import defaultdict
import dataclasses
import functools
import logging
import pprint
import re
from collections.abc import Sequence
from io import BytesIO
from tkinter import simpledialog
from typing import Literal, Mapping

import hydrus_api
from hydrus_api.types import FileHash, FileId, FileMetadata, FileRelationships, ServiceKey
from PIL import Image
from pydantic import TypeAdapter

from hydrustools.component.toolwindow import ToolWindow
from hydrustools.utils import hydrus, querylang
from hydrustools.utils.gui_util import flatList
from hydrustools.utils.inisettings import IniSettings
from hydrustools.utils.namespace import get_tag_unnamespaced_value
from hydrustools.utils.typedclient import TypedClient
from hydrustools.utils.util import chunk

from ..settings import settings_section

logger = logging.getLogger(__name__)

@settings_section(section="HydrusAPI")
class HyApiSettings(IniSettings):
    hydrus_api_key: str = "CHANGEME"
    hydrus_api_url: str = hydrus_api.DEFAULT_API_URL
    service_name_main_tags = "my tags"
    service_name_extra_tags = "downloader tags"
    service_name_favorites = "favourites"

@dataclasses.dataclass(frozen=True)
class TagInfo():
    count: int
    value: str

@dataclasses.dataclass(frozen=True)
class RelationshipInfo():
    tag: str
    ideal_tag: str
    siblings: frozenset[str]
    ancestors: frozenset[str]
    descendants: frozenset[str]


def set_api_key(new_api_key):
    HyApiSettings.hydrus_api_key = new_api_key


@dataclasses.dataclass()
class _HTWires():
    local_tags_service_key: str
    downloader_tags_service_key: str = None  # type: ignore

# HTWires = _HTWires()

client: TypedClient = None  # type: ignore

client_services: hydrus_api.Services = None  # type: ignore

local_tags_service_key: ServiceKey = None  # type: ignore
downloader_tags_service_key: ServiceKey = None  # type: ignore
favorites_service_key: ServiceKey = None  # type: ignore

# Data parsing, struct traversal

def get_service_key(services: hydrus_api.Services, type: hydrus_api.ServiceType, name: str) -> str:
    return next(
        k for k, v in services.items()
        if v["type"] == type.value and v["name"] == name
    )

def has_note(notename: str, max_n: int = 4) -> querylang.OrQuery:
    return [
        *[f'system:has note with name "{notename}"'],
        *[f'system:has note with name "{notename} ({n})"' for n in range(1, max_n)]
    ]

def local_tags(
    metadata: FileMetadata,
    type_: Literal['storage_tags', 'display_tags'] = 'display_tags',
    service_key: str | None = None
) -> list[str]:
    service_key = service_key or local_tags_service_key
    tagmap = metadata['tags'][service_key][type_]
    return tagmap.get(str(hydrus_api.TagStatus.CURRENT), [])

def get_hash_to_id_from_rels(file_relationships: dict[FileHash, FileRelationships]) -> dict[FileHash, FileId]:
    all_hashes = set()
    all_hashes.update(file_relationships.keys())
    all_hashes.update([r['king'] for r in file_relationships.values()])
    all_hashes.update(flatList([
        v for r in file_relationships.values()
        for v in r.values()
        if isinstance(v, list)
    ]))

    return {
        file["hash"]: file["file_id"]
        for file in
        client.get_file_metadata(
            hashes=[*all_hashes]
        )['metadata']
    }

# Queries

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

def get_relationship_info(
    target_tags: Sequence[str],
    service_key: str | None = None
) -> list[RelationshipInfo]:
    resp = client.get_siblings_and_parents(target_tags)
    service_key = service_key or local_tags_service_key

    return [
        RelationshipInfo(
            tag=tag_name,
            ideal_tag=v[service_key]["ideal_tag"],
            siblings=frozenset(v[service_key]["siblings"]),
            ancestors=frozenset(v[service_key]["ancestors"]),
            descendants=frozenset(v[service_key]["descendants"]),
        )
        for tag_name, v in resp["tags"].items()
    ]

@functools.cache
def get_render_scaled(file_id: int, width: int, height: int, max_width: int, max_height: int) -> Image.Image:
    ratio = min(max_width/width, max_height/height)
    resp = client.get_render(
        file_id=file_id,  # type: ignore
        height=int(ratio*height),
        width=int(ratio*width)
    )
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content))

@functools.cache
def get_thumb_scaled(file_id: int, max_width: int, max_height: int) -> Image.Image:
    resp = client.get_thumbnail(file_id=file_id)
    resp.raise_for_status()
    image = Image.open(BytesIO(resp.content))
    # ratio =min(max_width/image.width, max_height/image.height)
    image.thumbnail((max_width, max_height))
    return image


def addAltsToList(image_id_list: list[int]) -> list[int]:
    if len(image_id_list) == 0:
        return image_id_list

    file_relationships = client.get_file_relationships(
        file_ids=image_id_list
    )['file_relationships']

    # pprint.pprint(file_relationships)

    hash_to_id: dict[FileHash, FileId] = get_hash_to_id_from_rels(file_relationships)

    moved = set()
    for image_hash, rel_data in file_relationships.items():
        image_id = hash_to_id[image_hash]
        if image_id in moved:
            # logger.debug(f"{image_id} alts: Already touched self, skipping")
            continue
        try:
            image_index: int = image_id_list.index(image_id)
        except ValueError:
            logger.warning("Somehow, %s is in the relationships list but not the search list", image_hash)
            continue

        for rel_kind in [
            hydrus_api.DuplicateStatus.ALTERNATES,
            hydrus_api.DuplicateStatus.DUPLICATES,
            hydrus_api.DuplicateStatus.POTENTIAL_DUPLICATES,
        ]:
            rel_group = rel_data[str(rel_kind.value)]
            assert isinstance(rel_group, list)
            for rel_hash in rel_group:
                rel_id = hash_to_id[rel_hash]
                if rel_id in moved:
                    # logger.debug(f"{image_id} alts: Already touched {rel_id}, skipping")
                    continue

                # logger.debug(f"{rel_id!r}, {image_id_list!r}")
                if rel_id in image_id_list:
                    # Relocate
                    # logger.debug(f"{image_id} alts: Moving {rel_id} to index {image_index+1}")
                    image_id_list.remove(rel_id)
                    image_id_list.insert(image_index+1, rel_id)
                else:
                    # Add
                    # logger.debug(f"{image_id} alts: Adding new {rel_id} to index {image_index+1}")
                    image_id_list.insert(image_index+1, rel_id)

                # logger.debug(f"New list: {image_id_list}")
                # logger.debug(f"{image_id} alts: adding {rel_id} to moved set {moved}")
                moved.add(rel_id)
    return image_id_list


def add_implying_siblings(removed_tags: list[str]):
    """Extend a list of tags with any siblings that would imply
    any tag in the list. Used to fully delete a tag from an image."""
    resp = client.get_siblings_and_parents(removed_tags)
    for v in resp["tags"].values():
        if v[local_tags_service_key]['ideal_tag'] in removed_tags:
            for s in v[local_tags_service_key]['siblings']:
                if s not in removed_tags:
                    logger.warning(f"Also removing sibling tag {s}")
                    removed_tags.append(s)



# Database operations

def replace_tag(original_tag: str, new_tags: list[str], in_file_ids: list[int] | None = None) -> None:
    if in_file_ids:
        tagged_files = in_file_ids
    else:
        resp = client.search_files(
            tags=[original_tag],
            tag_service_key=local_tags_service_key
        )
        tagged_files = resp["file_ids"]
    # pprint.pprint(tagged_files)

    if len(tagged_files) < 1:
        logger.debug("Nothing to do!")
        return

    removed_tags = [original_tag]
    add_implying_siblings(removed_tags)

    logger.info(f"Replacing {original_tag!r} with {new_tags!r} in {len(tagged_files)} files")
    client.add_tags(
        file_ids=tagged_files,
        service_keys_to_actions_to_tags={
            local_tags_service_key: {
                hydrus_api.TagAction.ADD: new_tags,
                hydrus_api.TagAction.DELETE: removed_tags
            }
        }
    )


def flatten_tag_to_parents(source_tag: str):
    targets: list[RelationshipInfo] = get_relationship_info([source_tag])
    if len(targets) < 1:
        raise ValueError(f"Tag {source_tag!r} has no relationships")
    assert len(targets) == 1
    si = next(si for si in targets if si.tag == source_tag)

    if len(si.ancestors) < 1:
        raise ValueError(f"Tag {source_tag!r} has no ancestors in {si}")

    replace_tag(source_tag, list(si.ancestors))


def remove_tags_from_matches(query: querylang.AndQuery, remove_tags: list[str]):
    resp = client.search_files(
        tags=query,
        tag_service_key=local_tags_service_key
    )
    matching_files = resp['file_ids']

    # We also need to remove any siblings of these tags
    add_implying_siblings(remove_tags)

    logger.info(f"Removing {remove_tags!r} on {len(matching_files)} files matching {query}")
    if len(matching_files) == 0:
        logger.info("Nothing to do!")
        return

    client.add_tags(
        file_ids=matching_files,
        service_keys_to_actions_to_tags={
            local_tags_service_key: {
              hydrus_api.TagAction.DELETE: remove_tags
            }
        }
    )

def set_tag_list_of_images(
    tag_list: list[str],
    tool: ToolWindow | None,
    metadata_list: list[FileMetadata]
):
    if tool:
        logStage = tool.setStatus
    else:
        logStage = logger.info

    logStage(f"Setting {len(tag_list)} tags")
    file_ids = [m['file_id'] for m in metadata_list]

    client.add_tags(
        file_ids=file_ids,
        service_keys_to_tags={
            local_tags_service_key: tag_list,
        }
    )

    logger.debug(f"Checking differences: {[m['tags'] for m in metadata_list]=}")

    all_tags = set(flatList([
        local_tags(meta)
        for meta in metadata_list
    ]))

    logger.info("%s, %s", all_tags, set(tag_list))

    removed_tags = [*set(all_tags).difference(set(tag_list))]

    # We also need to remove any siblings of these tags
    add_implying_siblings(removed_tags)

    if removed_tags:
        logger.info(f"Removing tags: {removed_tags}")
        client.add_tags(
            file_ids=file_ids,
            service_keys_to_actions_to_tags={
                local_tags_service_key: {
                    hydrus_api.TagAction.DELETE: removed_tags
                }
            }
        )


def replace_tag_in_query(tag_name: str, new_tags: list[str], in_query: querylang.AndQuery):
    matching_files = client.search_files(
        tags=in_query,
        tag_service_key=local_tags_service_key
    )['file_ids']

    logger.info(f"Replacing {tag_name!r} with {new_tags!r} in {len(matching_files)} files matching {in_query}")
    replace_tag(tag_name, new_tags, matching_files)

def delete_all_query_matches(reason: str, query: hydrus_api.AndQuery):
    file_ids = client.search_files(
        tags=query,
        tag_service_key=local_tags_service_key
    )['file_ids']

    if len(file_ids) < 1:
        return
    logger.info(f"Deleting {len(file_ids)} images matching {query}")
    client.delete_files(
        file_ids=file_ids,
        reason=reason
    )


# Init

def init_client(tk=False) -> None:
    global client
    global local_tags_service_key
    global downloader_tags_service_key
    global favorites_service_key
    global client_services

    if not HyApiSettings.hydrus_api_key or HyApiSettings.hydrus_api_key == "CHANGEME":
        resp: str | None

        prompt = "Enter your Hydrus API key (found under Services > Review Services > local > client api)\nYou can change this or set a custom base url in the HTSettings.ini file."
        if tk:
            resp = simpledialog.askstring("API Key", prompt)
        else:
            print(prompt)
            resp = input("> ")

        if resp:
            if not re.match(r'[0-9a-f]{64}', resp):
                print(f"{resp!r} doesn't look like an API key. Things will probably not work.")
            else:
                print("Looks good!")

            HyApiSettings.hydrus_api_key = resp

    client = TypedClient(
        HyApiSettings.hydrus_api_key,
        HyApiSettings.hydrus_api_url
    )

    client_services = client.get_services()['services']

    TypeAdapter(hydrus_api.Services).validate_python(client_services)

    local_tags_service_key = get_service_key(
        client_services,
        hydrus_api.ServiceType.TAG_DOMAIN,
        HyApiSettings.service_name_main_tags
    )

    try:
        downloader_tags_service_key = get_service_key(
            client_services,
            hydrus_api.ServiceType.TAG_DOMAIN,
            HyApiSettings.service_name_extra_tags
        )
    except StopIteration:
        logger.exception(f"Missing a {HyApiSettings.service_name_extra_tags!r} tag group. Some things may break! This tool needs to be fixed to better support this case.")

    try:
        favorites_service_key = get_service_key(
            client_services,
            hydrus_api.ServiceType.LIKE_DISLIKE_RATING,
            HyApiSettings.service_name_favorites
        )
    except StopIteration:
        logger.exception(f"Missing a {HyApiSettings.service_name_favorites!r} tag group. Some things may break! This tool needs to be fixed to better support this case.")


if __name__ == "__main__":
    init_client()


def apply_tagset_groups(
    group_namespace: str,
    groups: Mapping[frozenset[str], list[hydrus_api.FileMetadata]],
    total=False
):
    all_tags_in_namespace = [ti.value for ti in hydrus.search_tags_re(f"{group_namespace}:*", subpattern=None)]

    all_tagsets: list[frozenset] = [*groups.keys()]
    group_names = {}

    add_tags: defaultdict[str, list[int]] = defaultdict(list)

    # Gather pending add operations
    for i, (tagset, items) in enumerate(groups.items()):
        if len(items) == 0:
            continue

        # Clean up names
        name_tagset = set()
        for n in tagset:
            if not all(n in set for set in all_tagsets) and not n.startswith("-"):
                name_tagset.add(get_tag_unnamespaced_value(n))

        if len(tagset) == 0:
            name_tagset.add("emptyset")
        if len(name_tagset) == 0:
            n = next(iter(tagset))
            name_tagset.add(get_tag_unnamespaced_value(n))

        tagname = f"{group_namespace}:{', '.join(sorted(name_tagset))}"

        add_tags[tagname].extend([i["file_id"] for i in items])

    remove_tags: defaultdict[str, list[int]] = defaultdict(list)

    if total:
        file_ids = client.search_files(
            tags=[f"{group_namespace}:*"]
        )['file_ids']

        for id_chunk in chunk(file_ids, 200):
            metadata = hydrus.client.get_file_metadata(file_ids=id_chunk)['metadata']
            for file_md in metadata:
                file_id = file_md["file_id"]
                my_local_tags = local_tags(file_md)
                for ns_tag in all_tags_in_namespace:
                    if ns_tag in my_local_tags:
                        if file_id in add_tags[ns_tag]:
                            add_tags[ns_tag].remove(file_id)
                        else:
                            # logger.debug(f"Tag {ns_tag=} in {my_local_tags=} but not {add_tags[ns_tag]=}, need to remove")
                            remove_tags[ns_tag].append(file_id)

    # Apply operations
    for tagname, id_list in add_tags.items():
        if len(id_list) < 1:
            continue
        logger.info(f"Adding tag {tagname} to {len(id_list)} images")
        hydrus.client.add_tags(
            file_ids=id_list,
            service_keys_to_actions_to_tags={
                hydrus.local_tags_service_key: {
                    hydrus_api.TagAction.ADD: [tagname]
                }
            }
        )

    for tagname, id_list in remove_tags.items():
        if len(id_list) < 1:
            continue
        logger.info(f"Removing tag {tagname} from {len(id_list)} images")
        hydrus.client.add_tags(
            file_ids=id_list,
            service_keys_to_actions_to_tags={
                hydrus.local_tags_service_key: {
                    hydrus_api.TagAction.DELETE: [tagname]
                }
            }
        )
    logger.info("Divided images into %s groups.", len(groups))

