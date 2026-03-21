from collections import OrderedDict
import dataclasses
import functools


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


@functools.lru_cache()
def get_tag_namespace(tag: str) -> None | Namespace:
    if ":" not in tag:
        return None
    ns = tag.split(":")[0]
    ns = ns.removeprefix('-')
    return namespace_map.get(ns) or Namespace(ns)


@functools.lru_cache()
def get_tag_unnamespaced_value(tag: str) -> str:
    if ":" not in tag:
        return tag
    val = tag.split(":")[1]
    return val


@functools.lru_cache()
def get_tag_color(tag: str) -> None | str:
    namespace = get_tag_namespace(tag)
    if not namespace:
        return "#006ffa"
    return namespace.color


@functools.lru_cache()
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