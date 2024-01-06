import os, sys

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from namu_gpt.chatbot import NamuAgent

if __name__ == "__main__":
    url = "https://namu.wiki/w/%EB%A9%94%EC%9D%B4%ED%94%8C%EC%8A%A4%ED%86%A0%EB%A6%AC/%EB%A0%88%EB%B2%A8%EB%B3%84%20%EC%9C%A1%EC%84%B1"  # 메이플스토리
    question = "입문자인데. 캐릭터를 잘 육성할 수 있는 팁 좀 알려줘"

    agent = NamuAgent()
    data = agent.recursive_load(start_url=url)
    qabot = agent.initialize_multi_retrieval_qabot(
        agent.intialize_multiple_retrievers(data)
    )

    msg = f"""
        질문 : 
        {question}

        ===================================================================================================

        대답 : 
        {qabot(question)["result"]}
    """
    print(msg)
