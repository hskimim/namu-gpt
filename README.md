# Namu GPT

나무위키 사이트의 문서를 구조화하여 vector db의 형태로 만들어 전반적으로 langchain 기능들을 사용, RAG 기반 chatbot을 만듭니다.
초기에 설정된 url 을 설정하면 정해진 깊이나 개수만큼 recursive 하게 나무위키의 하이퍼링크를 타고 들어가며 데이터를 축적합니다. (기존 langchain 의 RecursiveUrlLoader 수정)