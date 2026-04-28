import abc
import argparse
import json
import logging
import os
import pprint
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import KW_ONLY, asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, TypedDict
from urllib.parse import quote, urlparse

# from hydrustools.utils.argparse_formatter import HTApFmtCls

logger = logging.getLogger(__name__)

@dataclass
class SiteModel():
    _: KW_ONLY
    gallerydl_extractor: str | None = None

    @abc.abstractmethod
    def get_file_url(self, domain: str, file_id: str) -> str: ...

    @abc.abstractmethod
    def get_tag_url(self, domain: str, tags: list[str]) -> str: ...

    @staticmethod
    def from_dump(data: dict) -> 'SiteModel':
        clsn = data.pop('_model')
        cls = globals()[clsn]
        if not issubclass(cls, SiteModel):
            raise TypeError(f"No model class {clsn}")
        return cls(**data)

    def dump(self) -> dict:
        return {
            **asdict(self),
            "_model": str(self.__class__.__name__)
        }

@dataclass
class BooruSiteModel(SiteModel):
    fmt_file_url: str
    fmt_query_url: str
    tag_sep: str = " "

    def get_file_url(self, domain: str, file_id: str) -> str:
        return self.fmt_file_url.format(domain=domain, id=file_id)

    def get_tag_url(self, domain: str, tags: list[str]) -> str:
        tagstr = quote(self.tag_sep.join(tags))
        params: defaultdict[str, Any] = defaultdict(lambda: '')
        params.update(domain=domain, tags=tagstr)
        return self.fmt_query_url.format_map(params)


domain_to_cat: dict[str, str] = {
    'e621': 'E621',
}
cat_to_model: dict[str, SiteModel] = {
    "Szurubooru": BooruSiteModel(
        fmt_file_url="https://{domain}/post/{id}",
        fmt_query_url="https://{domain}/posts/query={tags}",
        gallerydl_extractor='szurubooru'
    ),
    "E621": BooruSiteModel(
        fmt_file_url="https://{domain}/posts/{id}",
        fmt_query_url="https://{domain}/posts?tags={tags}",
    ),
    "FurAffinity": BooruSiteModel(
        fmt_file_url="https://{domain}/view/{id}",
        fmt_query_url="https://{domain}/search/?q={tags}",
    ),
    "Rule34.us Gelbooru": BooruSiteModel(
        fmt_file_url="https://{domain}/index.php?r=posts/view&id={id}",
        fmt_query_url="https://{domain}/index.php?r=posts/index&q={tags}"
    ),
}

map_cat_to_extractor: dict[str, str] = {
    "Gelbooru (0.1)": 'gelbooru_v01',
    "Shimmie": 'shimmie2',
    # "Gelbooru (0.2)": 'gelbooru_v02'
}

def init_sites():
    # global domain_to_cat

    localappdata: str = os.environ.get("LOCALAPPDATA") # type: ignore
    sites_dir = Path(localappdata, "Bionus", "Grabber", "sites")

    for site_dir in sites_dir.glob('*/'):
        site_cat = site_dir.name

        for site_inst in site_dir.glob('*/'):
            domain = site_inst.name
            domain_to_cat[domain] = site_cat
            # print(f"Added domain_to_cat: {domain} = {site_cat}", file=sys.stderr)

        model_xml = site_dir.joinpath('model.xml')
        if model_xml.exists():
            tree = ET.parse(model_xml)
            site: ET.Element[str] = tree.getroot()

            try:
                query_page = site.find("Urls/Html/Tags").text # type: ignore
                # if '{pagepart}' in query_page:
                #     query_page = query_page.replace('{pagepart}')

                cat_to_model[site_cat] = BooruSiteModel(
                    # gallerydl_extractor=site_cat,
                    fmt_file_url="https://{domain}" + site.find("Urls/Html/Post").text, # type: ignore
                    fmt_query_url="https://{domain}" + query_page, # type: ignore
                    # tag_sep=site.find("TagFormat/WordSeparator").text
                )
                if map_cat_to_extractor.get(site_cat):
                    cat_to_model[site_cat].gallerydl_extractor = map_cat_to_extractor.get(site_cat)
                # print(f"Added cat_to_model: {site_cat}", file=sys.stderr)
            except TypeError:
                raise ValueError(model_xml)
        else:
            continue

# Library methods

def _get_model(domain) -> SiteModel:
    if domain not in domain_to_cat:
        init_sites()
    try:
        cat = domain_to_cat[domain]
    except KeyError as e:
        raise NotImplementedError(f"No known type for domain {domain}") from e

    if cat not in cat_to_model:
        init_sites()
    try:
        return cat_to_model[cat]
    except KeyError as e:
        raise NotImplementedError(f"No parsing model for source type {cat}") from e


def get_file_url(domain: str, file_id: str) -> str:
    return _get_model(domain).get_file_url(domain, file_id)

def get_tag_url(domain: str, tags: list[str]) -> str:
    return _get_model(domain).get_tag_url(domain, tags)

class SitesAndModels(TypedDict):
    models: dict[str, dict[str, Any]]
    sites: dict[str, str]

def export_models() -> SitesAndModels:
    init_sites()
    return {
        "models": {
            k: v.dump()
            for k, v in cat_to_model.items()
        },
        "sites": domain_to_cat
    }

def import_models(models: SitesAndModels):
    cat_to_model.update({
        name: SiteModel.from_dump(ad)
        for name, ad in models['models'].items()
    })
    domain_to_cat.update(models['sites'])

# CLI

def cli_dump_models(args):
    file = Path("./models.json")
    with open(file, "w") as fp:
        models: SitesAndModels = export_models()
        json.dump(models, fp, indent=2)

    summary = {k: len(v) for k, v in models.items()} # type: ignore
    print("Write", summary, "to", file)

def define_parser(parser):
    parser.description="""Convert booru between semantic and booru-formatted URLs, with different formatters used for different booru types, which are mapped to different server types.

This comes pre-supplied with a few common models but will also attempt to use existing configuration data to load booru models.
The currently implemented metadata sources are:
- Grabber (Known sites)
- Grabber (XML format)

This is the CLI utility. This file can also be used as a python library."""

    subparsers = parser.add_subparsers(dest="action", metavar="ACTION")
    subparsers.required = True

    parser.add_argument("-m", "--load-models", help="Path to a models file. These models will be added to the preinstalled models and any discovered models.")

    get_files = subparsers.add_parser(
        "get_files", help="Get urls to files as a json list of strings."
    )
    get_files.add_argument("domain", help="Web domain of service")
    get_files.add_argument("file_ids", nargs="+", help="Numerical file IDs")
    get_files.add_argument(
        "-g", "--gallerydl-hints", action="store_true",
        help="Prepend output URLs with a gallerydl extractor prefix, if known.")

    def parser_get_files(args):
        hint_prefix = ''
        if args.gallerydl_hints:
            model = _get_model(args.domain)
            if model.gallerydl_extractor:
                hint_prefix = f"{model.gallerydl_extractor}:"

        urls = [
                hint_prefix + get_file_url(args.domain, file_id)
                for file_id in args.file_ids
            ]
        print(
            json.dumps(urls, indent=2)
        )

    get_files.set_defaults(func=parser_get_files)


    get_search = subparsers.add_parser(
        "get_search", help="Get the URL for a search. Returns one URL joining all tags."
    )
    get_search.add_argument("domain", help="Web domain of service")
    get_search.add_argument("tags", nargs="+")
    get_search.add_argument(
        "-g", "--gallerydl-hints", action="store_true",
        help="Prepend output URLs with a gallerydl extractor prefix, if known.")

    def parser_get_search(args):
        hint_prefix = ''
        if args.gallerydl_hints:
            model = _get_model(args.domain)
            if model.gallerydl_extractor:
                hint_prefix = f"{model.gallerydl_extractor}:"

        print(
            hint_prefix +
            get_tag_url(args.domain, args.tags)
        )

    get_search.set_defaults(func=parser_get_search)

    dump_models = subparsers.add_parser("dump_models", help="Load all available models from useru context, then write model info to models.json")
    dump_models.set_defaults(func=cli_dump_models)

    return parser

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    define_parser(parser)
    args = parser.parse_args()

    if args.load_models:
        with open(args.load_models, "r") as fp:
            import_models(json.load(fp))

    args.func(args)

