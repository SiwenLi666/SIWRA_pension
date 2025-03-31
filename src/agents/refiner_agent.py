from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.retriever.retriever_tool import RetrieverTool
import logging

logger = logging.getLogger(__name__)
class RefinerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.7)
        self.retriever = RetrieverTool()
        self.attempts = {}

    def refine(self, state):
        conversation_id = state.get("conversation_id")
        attempts_so_far = self.attempts.get(conversation_id, 0)
        self.attempts[conversation_id] = attempts_so_far + 1
        logger.info(f"[refine_answer] attempt #{attempts_so_far + 1}")

        # 1. Reformulate query
        question = state.get("question", "")
        messages = [
            SystemMessage(content="You are a helpful assistant. Reformulate the question to make it more specific or clearer."),
            HumanMessage(content=f"Original question: {question}")
        ]
        reformulated = self.llm.invoke(messages).content.strip()
        logger.info(f"[refine_answer] Reformulated question: {reformulated}")

        # 2. Retrieve again
        new_docs = self.retriever.retrieve_relevant_docs(reformulated, top_k=3)
        context = "\n\n".join([doc.page_content for doc in new_docs])
        
        # 3. Regenerate answer
        answer_prompt = [
            SystemMessage(content="Use the following context to answer the user's question as clearly and helpfully as possible."),
            HumanMessage(content=f"Question: {reformulated}\n\nContext:\n{context}")
        ]
        new_answer = self.llm.invoke(answer_prompt).content.strip()

        # 4. Decide route
        route = "retry" if attempts_so_far + 1 < 2 else "give_up"
        return {
            **state,
            "draft_answer": new_answer,
            "retrieved_docs": new_docs,
            "route": route
        }

    def route_refinement(self, state):
        return state.get("route", "give_up")
