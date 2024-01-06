from __future__ import annotations
from copy import copy
import asyncio
import logging
import re
from typing import (
    TYPE_CHECKING,
    Callable,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Union,
)

import requests

from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse

from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseLoader

# from langchain.utils.html import custom_extract_sub_links


def find_all_links(
    raw_html: str, *, pattern: Union[str, re.Pattern, None] = None
) -> List[str]:
    """Extract all links from a raw html string.

    Args:
        raw_html: original html.
        pattern: Regex to use for extracting links from raw html.

    Returns:
        List[str]: all links
    """
    return list(set(re.findall(pattern, raw_html)))


def custom_extract_sub_links(
    raw_html: str,
    url: str,
    *,
    base_url: Optional[str] = None,
    prefix_url: Optional[str] = None,
    pattern: Union[str, re.Pattern, None] = None,
) -> List[str]:
    """Extract all links from a raw html string and convert into absolute paths.

    Args:
        raw_html: original html.
        url: the url of the html.
        base_url: the base url to check for outside links against.
        pattern: Regex to use for extracting links from raw html.
        prevent_outside: If True, ignore external links which are not children
            of the base url.
        exclude_prefixes: Exclude any URLs that start with one of these prefixes.

    Returns:
        List[str]: sub links
    """
    base_url = base_url if base_url is not None else url
    all_links = find_all_links(
        raw_html, pattern=pattern
    )  # all href are started with "'/w/'"
    absolute_paths = set()
    for link in all_links:
        # Some may be absolute links like https://to/path
        if link.startswith("http"):
            absolute_paths.add(link)
        # Some may have omitted the protocol like //to/path
        elif link.startswith("//"):
            absolute_paths.add(f"{urlparse(url).scheme}:{link}")
        elif prefix_url:
            absolute_paths.add(urljoin(prefix_url, link))
        else:
            absolute_paths.add(urljoin(url, link))
    return list(absolute_paths)


if TYPE_CHECKING:
    import aiohttp

logger = logging.getLogger(__name__)


def _metadata_extractor(raw_html: str, url: str) -> dict:
    """Extract metadata from raw html using BeautifulSoup."""
    metadata = {"source": url}

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning(
            "The bs4 package is required for default metadata extraction. "
            "Please install it with `pip install bs4`."
        )
        return metadata
    soup = BeautifulSoup(raw_html, "html.parser")
    if title := soup.find("title"):
        metadata["title"] = title.get_text()
    if description := soup.find("meta", attrs={"name": "description"}):
        metadata["description"] = description.get("content", None)
    if html := soup.find("html"):
        if html.get("lang", None):
            metadata["language"] = html.get("lang", None)
    return metadata


NAMUWIKI_HEADER = "https://namu.wiki"

MAIN_TAG = "_1+UTAYHc"
TITLE_TAG = "wiki-heading"
TEXT_TAG = "wiki-heading-content"
DEFAULT_REGEX = r"href='(/w/[^']+)'"


def _extractor(raw_html: str, url) -> dict[str, str]:
    dom = BeautifulSoup(raw_html, "lxml")
    try:
        main_tag = dom.find_all("div", {"class": MAIN_TAG})[0]

        titles = [
            div.text
            for div in main_tag.find_all(
                [f"h{ii}" for ii in range(1, 10)], {"class": TITLE_TAG}
            )
        ]
        texts = [div.text for div in main_tag.find_all("div", {"class": TEXT_TAG})]
    except Exception as e:
        raise ValueError(url, e)
    if len(titles) != len(texts):
        raise ValueError(f"|title|({len(titles)}) != |text|({len(texts)})")

    return dict(zip(titles, texts))


class NamuRecursiveUrlLoader(BaseLoader):
    """Load all child links from a URL page."""

    def __init__(
        self,
        url: str,
        max_depth: Optional[int] = 2,
        max_length: Optional[int] = 500,
        use_async: Optional[bool] = None,
        timeout: Optional[int] = 10,
        link_regex: Union[str, re.Pattern, None] = DEFAULT_REGEX,
        headers: Optional[dict] = None,
        check_response_status: bool = False,
    ) -> None:
        """Initialize with URL to crawl and any subdirectories to exclude.
        Args:
            url: The URL to crawl.
            max_depth: The max depth of the recursive loading.
            use_async: Whether to use asynchronous loading.
                If True, this function will not be lazy, but it will still work in the
                expected way, just not lazy.
            exclude_dirs: A list of subdirectories to exclude.
            timeout: The timeout for the requests, in the unit of seconds. If None then
                connection will not timeout.
            prevent_outside: If True, prevent loading from urls which are not children
                of the root url.
            link_regex: Regex for extracting sub-links from the raw html of a web page.
            check_response_status: If True, check HTTP response status and skip
                URLs with error responses (400-599).
        """

        self.url = url
        self.max_depth = max_depth if max_depth is not None else 2
        self.max_length = max_length if max_length is not None else 500
        self.use_async = use_async if use_async is not None else False
        self.extractor = _extractor
        self.metadata_extractor = _metadata_extractor

        self.timeout = timeout
        self.link_regex = link_regex
        self._lock = asyncio.Lock() if self.use_async else None
        self.headers = headers
        self.check_response_status = check_response_status

        self._trajectory = 0

    def _get_child_links_recursive(
        self, url: str, visited: Set[str], max_length: int, depth: int = 0
    ) -> Iterator[List[Document]]:
        """Recursively get all child links starting with the path of the input URL.

        Args:
            url: The URL to crawl.
            visited: A set of visited URLs.
            depth: Current depth of recursion. Stop when depth >= max_depth.
        """

        if depth >= self.max_depth:
            return

        if max_length < self._trajectory:
            return

        # Get all links that can be accessed from the current URL
        visited.add(url)
        try:
            response = requests.get(url, timeout=self.timeout, headers=self.headers)
            if self.check_response_status and 400 <= response.status_code <= 599:
                raise ValueError(f"Received HTTP status {response.status_code}")
        except Exception as e:
            logger.warning(
                f"Unable to load from {url}. Received error {e} of type "
                f"{e.__class__.__name__}"
            )
            return
        content = self.extractor(response.text, url)
        meta = self.metadata_extractor(response.text, url)
        if len(content):
            doc = []
            for sub_title, section in content.items():
                meta["topic"] = sub_title

                doc.append(
                    Document(
                        page_content=section,
                        metadata=copy(meta),
                    )
                )
            yield doc

        # Store the visited links and recursively visit the children
        sub_links = custom_extract_sub_links(
            response.text,
            url,
            base_url=self.url,
            prefix_url=NAMUWIKI_HEADER,
            pattern=self.link_regex,
        )
        for link in sub_links:
            # Check all unvisited links
            if link not in visited:
                yield from self._get_child_links_recursive(
                    link, visited, max_length, depth=depth + 1
                )
                self._trajectory += 1

    async def _async_get_child_links_recursive(
        self,
        url: str,
        visited: Set[str],
        *,
        session: Optional[aiohttp.ClientSession] = None,
        depth: int = 0,
    ) -> List[Document]:
        """Recursively get all child links starting with the path of the input URL.

        Args:
            url: The URL to crawl.
            visited: A set of visited URLs.
            depth: To reach the current url, how many pages have been visited.
        """
        try:
            import aiohttp
        except ImportError:
            raise ImportError(
                "The aiohttp package is required for the RecursiveUrlLoader. "
                "Please install it with `pip install aiohttp`."
            )
        if depth >= self.max_depth:
            return []

        # Disable SSL verification because websites may have invalid SSL certificates,
        # but won't cause any security issues for us.
        close_session = session is None
        session = (
            session
            if session is not None
            else aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers=self.headers,
            )
        )
        async with self._lock:  # type: ignore
            visited.add(url)
        try:
            async with session.get(url) as response:
                text = await response.text()
                if self.check_response_status and 400 <= response.status <= 599:
                    raise ValueError(f"Received HTTP status {response.status}")
        except (aiohttp.client_exceptions.InvalidURL, Exception) as e:
            logger.warning(
                f"Unable to load {url}. Received error {e} of type "
                f"{e.__class__.__name__}"
            )
            if close_session:
                await session.close()
            return []
        results = []
        content = self.extractor(text)
        if content:
            results.append(
                Document(
                    page_content=content,
                    metadata=self.metadata_extractor(text, url),
                )
            )
        if depth < self.max_depth - 1:
            sub_links = custom_extract_sub_links(
                text,
                url,
                base_url=self.url,
                pattern=self.link_regex,
                prefix_url=NAMUWIKI_HEADER,
            )

            # Recursively call the function to get the children of the children
            sub_tasks = []
            async with self._lock:  # type: ignore
                to_visit = set(sub_links).difference(visited)
                for link in to_visit:
                    sub_tasks.append(
                        self._async_get_child_links_recursive(
                            link, visited, session=session, depth=depth + 1
                        )
                    )
            next_results = await asyncio.gather(*sub_tasks)
            for sub_result in next_results:
                if isinstance(sub_result, Exception) or sub_result is None:
                    # We don't want to stop the whole process, so just ignore it
                    # Not standard html format or invalid url or 404 may cause this.
                    continue
                # locking not fully working, temporary hack to ensure deduplication
                results += [r for r in sub_result if r not in results]
        if close_session:
            await session.close()
        return results

    def lazy_load(self) -> Iterator[Document]:
        """Lazy load web pages.
        When use_async is True, this function will not be lazy,
        but it will still work in the expected way, just not lazy."""
        visited: Set[str] = set()
        if self.use_async:
            results = asyncio.run(
                self._async_get_child_links_recursive(self.url, visited)
            )
            return iter(results or [])
        else:
            return self._get_child_links_recursive(self.url, visited, self.max_length)

    def load(self) -> List[Document]:
        """Load web pages."""
        return list(self.lazy_load())
