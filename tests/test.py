import os, sys

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from namu_gpt.chatbot import NamuAgent

if __name__ == "__main__":
    url = "https://namu.wiki/w/메이플스토리/레벨별%20육성"
    agent = NamuAgent(url, verbose=True)

    # RAG based Q/A
    question = "메이플스토리 입문자인데. 캐릭터를 잘 육성할 수 있는 팁 좀 알려줘"
    answer = agent(question)

    msg = f"""
        질문 : 
        {question}

        ===================================================================================================

        대답 : 
        {answer}
    """
    print(msg)

    ## get hierarchy documents with NamuWiki link
    # url = "https://namu.wiki/w/메이플스토리/세계관"
    # documents = agent.namu_retriever.get_namu_hierachy_docs(url)
