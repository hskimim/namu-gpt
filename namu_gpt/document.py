import re
from copy import copy

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

import tiktoken
from dotenv import load_dotenv

load_dotenv(verbose=True)

tokenizer = tiktoken.get_encoding("p50k_base")


# create the length function
def tiktoken_len(text):
    tokens = tokenizer.encode(text, disallowed_special=())
    return len(tokens)


text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=100,
    length_function=tiktoken_len,
)


class HierachicalDocuments:
    def __init__(self, data) -> None:
        self.data: list[list[Document]] = data

    def _cleanse(self, docs: list[Document]) -> list[Document]:
        prep_data = copy(docs)

        for d in prep_data:
            tmp = d.metadata

            tmp["title"] = tmp["title"].replace("- 나무위키", "").strip()

            topic = tmp["topic"].replace("[편집]", "")
            topic = re.sub(r"\d+\.\s*", "", topic).strip()

            content = d.page_content
            d.page_content = f"{topic} - {content}"

            del tmp["topic"]
            del tmp["source"]
        return prep_data

    def _retokenize(self, docs: list[Document]) -> list[Document]:
        retokenized_docs = []

        for doc in docs:
            meta = doc.metadata
            tokenized = text_splitter.create_documents([doc.page_content])
            for idx in range(len(tokenized)):
                tokenized[idx].metadata = meta
            retokenized_docs += tokenized
        return retokenized_docs

    def postprocess_txt(self) -> list[list[Document]]:
        postprocessed = [self._cleanse(doc) for doc in self.data]
        return [self._retokenize(doc) for doc in postprocessed]
