from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.chains.router import MultiRetrievalQAChain

from namu_gpt import constant
from namu_gpt.crawler import NamuRecursiveUrlLoader
from namu_gpt.document import HierachicalDocuments

from dotenv import load_dotenv
import logging

load_dotenv(verbose=True)
logger = logging.getLogger().setLevel(logging.INFO)


class NamuRetriever:
    def __init__(self, url, max_depth, max_length, verbose) -> None:
        self.url: str = url
        self.max_depth: int = max_depth
        self.max_length: int = max_length
        self.verbose: bool = verbose

    def _recursive_load(
        self,
        url: str | None = None,
    ) -> HierachicalDocuments:
        if self.verbose:
            logging.info("[recursive_load] started...")
        docs = NamuRecursiveUrlLoader(
            url=self.url if url is None else url,
            max_depth=self.max_depth,
            max_length=self.max_length,
        ).load()
        return HierachicalDocuments(data=docs)

    def _intialize_multiple_retrievers(
        self,
        documents: HierachicalDocuments,
    ) -> list[dict]:
        if self.verbose:
            logging.info("[intialize_multiple_retrievers] started...")
        retriever_infos = []

        for splitted_doc in documents.postprocess_txt():
            retreiver = Chroma.from_documents(
                documents=splitted_doc,
                embedding=OpenAIEmbeddings(model=constant.TEXT_EMBEDDING_MODEL_NAME),
            ).as_retriever()

            title = splitted_doc[0].metadata["title"]
            content = constant.DESC_PROMPT.format(title=title)
            dict_ = {
                "name": title,
                "description": content,
                "retriever": retreiver,
            }

            retriever_infos.append(dict_)
        return retriever_infos

    def _initialize_multi_retrieval_qabot(
        self,
        multi_retrievers: list[dict],
        verbose: bool = True,
    ) -> MultiRetrievalQAChain:
        if self.verbose:
            logging.info("[initialize_multi_retrieval_qabot] started...")

        chain = MultiRetrievalQAChain.from_retrievers(
            ChatOpenAI(model=constant.LLM_MODEL_NAME),
            multi_retrievers,
            verbose=verbose,
        )
        return chain

    def _init_agent(self, verbose: bool) -> MultiRetrievalQAChain:
        retrievers = self._intialize_multiple_retrievers(self._recursive_load())
        return self._initialize_multi_retrieval_qabot(retrievers, verbose)

    def get_namu_hierachy_docs(self, url: str | None = None) -> HierachicalDocuments:
        return self._recursive_load(url)
