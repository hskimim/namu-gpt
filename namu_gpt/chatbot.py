from langchain.schema import SystemMessage
from langchain.memory import ChatMessageHistory
from namu_gpt.retriever import NamuRetriever


class NamuAgent:
    def __init__(
        self,
        url: str,
        max_depth: int = 2,
        max_length: int = 1000,
        system_prompt: str | None = "You are a helpful assistant.",
        memory: bool = True,
        verbose: bool = False,
    ) -> None:
        self._url = url
        self._retriever = NamuRetriever(url, max_depth, max_length, verbose)
        self._namu_agent = self._retriever._init_agent(verbose)
        self.memory = memory

        if memory:
            self._chat_history = ChatMessageHistory()
            if system_prompt:
                self._chat_history.add_message(SystemMessage(content=system_prompt))

    def __call__(self, query: str) -> str:
        if self.memory:
            self._chat_history.add_user_message(query)
        msg = self._namu_agent(self._chat_history)
        if self.memory:
            self._chat_history.add_ai_message(msg["result"])
        return msg["result"]

    @property
    def chat_history(self):
        return self._chat_history

    @property
    def namu_retriever(self) -> NamuRetriever:
        return self._retriever
