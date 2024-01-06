import re
from copy import deepcopy
from pydantic import BaseModel

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

embedder = OpenAIEmbeddings(model=constant.TEXT_EMBEDDING_MODEL_NAME)
llm = ChatOpenAI(model=constant.LLM_MODEL_NAME)


class NamuAgent:
    def recursive_load(
        self,
        start_url: str,
        max_depth: int = 2,
        max_length: int = 1000,
    ) -> HierachicalDocuments:
        logging.info("[recursive_load]")
        docs = NamuRecursiveUrlLoader(
            url=start_url,
            max_depth=max_depth,
            max_length=max_length,
        ).load()
        return HierachicalDocuments(data=docs)

    def intialize_multiple_retrievers(
        self,
        documents: HierachicalDocuments,
    ) -> list[dict]:
        logging.info("[intialize_multiple_retrievers]")
        retriever_infos = []

        for splitted_doc in documents.postprocess_txt():
            retreiver = Chroma.from_documents(
                documents=splitted_doc,
                embedding=embedder,
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

    def initialize_multi_retrieval_qabot(
        self,
        multi_retrievers: list[dict],
        verbose: bool = True,
    ) -> MultiRetrievalQAChain:
        logging.info("[initialize_multi_retrieval_qabot]")
        chain = MultiRetrievalQAChain.from_retrievers(
            llm,
            multi_retrievers,
            verbose=verbose,
        )
        return chain
