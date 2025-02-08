import gradio as gr
import requests
import logging
import threading
import time
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    MessagesPlaceholder
)
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# URL Ollama API
OLLAMA_API = "http://ollama:11434"

# Флаг остановки генерации
stop_flag = threading.Event()

# Проверка подключения к Ollama перед запуском
def test_ollama_connection(retries=3, delay=3):
    for i in range(retries):
        try:
            response = requests.get(f"{OLLAMA_API}/api/tags", timeout=5)
            response.raise_for_status()
            logging.info("✅ Успешное подключение к Ollama")
            return True
        except requests.exceptions.RequestException as e:
            logging.warning(f"❌ Ошибка подключения ({i+1}/{retries}): {e}")
            time.sleep(delay)
    logging.error("🚨 Не удалось подключиться к Ollama после нескольких попыток")
    return False

if not test_ollama_connection():
    exit(1)  # Прерываем запуск, если Ollama недоступен

# Запускаем тестовое подключение
test_ollama_connection()

# Инициализация движка LLM
def get_llm_engine(model_name):
    return ChatOllama(
        model=model_name,
        base_url=OLLAMA_API,
        temperature=0.3
    )

# Настройки системного промпта
SYSTEM_TEMPLATE = """You are an expert AI coding assistant. Provide concise, correct solutions 
with strategic print statements for debugging. Always respond in English."""

chat_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_TEMPLATE),
    MessagesPlaceholder(variable_name="chat_history"),
    HumanMessagePromptTemplate.from_template("{input}")
])
class ChatBot:
    def __init__(self):
        self.chat_history = [AIMessage(content="Hi! I'm DeepSeek. How can I help you code today? 💻")]

    def generate_ai_response(self, user_input, llm_engine):
        stop_flag.clear()  # Сбрасываем флаг перед генерацией

        if stop_flag.is_set():
            logging.warning("⛔ Генерация остановлена пользователем")
            return "⚠️ Остановлено пользователем"

        logging.info(f"📝 Отправка запроса: {user_input}")
        self.chat_history.append(HumanMessage(content=user_input))

        try:
            chain = chat_prompt | llm_engine | StrOutputParser()
            response = chain.invoke({"input": user_input, "chat_history": self.chat_history}) or "⚠️ Ошибка: модель не вернула ответ."
        except Exception as e:
            logging.error(f"❌ Ошибка генерации: {e}")
            response = "⚠️ Ошибка обработки запроса."

        self.chat_history.append(AIMessage(content=response))
        logging.info(f"💡 Полный ответ от модели: {response}")

        return response

    def chat(self, message, model_choice, history):
        """Обработка чата в Gradio"""
        if not message:
            return "", history, history

        logging.debug(f"📩 Входящее сообщение: {message}")
        logging.debug(f"🔄 Выбранная модель: {model_choice}")

        # Инициализация LLM-движка
        llm_engine = get_llm_engine(model_choice)
        logging.debug("✅ LLM-движок успешно инициализирован")

        # Генерация ответа
        ai_response = self.generate_ai_response(message, llm_engine)

        # Обновляем историю сообщений
        history.append((message, ai_response))

        return "", history, history # Очищаем поле ввода

    def stop_generation(self):
        """Остановка генерации"""
        logging.warning("⛔ Остановка генерации пользователем")
        stop_flag.set()

    def clear_chat(self):
        """Очистка чата"""
        logging.info("🗑 Очистка истории чата")
        self.chat_history = [
            AIMessage(content="Hi! I'm DeepSeek. How can I help you code today? 💻")
        ]
        return [], []


def create_demo():
    chatbot = ChatBot()
    
    with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue", neutral_hue="zinc")) as demo:
        gr.Markdown("# 🧠 DeepSeek Code Companion")
        gr.Markdown("🚀 Your AI Pair Programmer with Debugging Superpowers")
        
        history_state = gr.State([])  # Храним историю сообщений
        
        with gr.Row():
            with gr.Column(scale=4):
                chatbot_component = gr.Chatbot(value=[], height=500, type="messages")
                
                msg = gr.Textbox(
                    placeholder="Type your coding question here...",
                    show_label=False
                )
                
                with gr.Row():
                    stop_btn = gr.Button("⛔ Stop")
                    clear_btn = gr.Button("🗑 Clear")
                
            with gr.Column(scale=1):
                model_dropdown = gr.Dropdown(
                    choices=["deepseek-r1:1.5b", "deepseek-r1:7b", "deepseek-r1:14b"],
                    value="deepseek-r1:1.5b",
                    label="Choose Model"
                )
                gr.Markdown("### Model Capabilities")
                gr.Markdown("""
                - 🐍 Python Expert
                - 🐞 Debugging Assistant
                - 📝 Code Documentation
                - 💡 Solution Design
                """)
                
                gr.Markdown("Built with [Ollama](https://ollama.ai/) | [LangChain](https://python.langchain.com/)")

        # Обрабатываем ввод сообщений
        msg.submit(
            fn=chatbot.chat,
            inputs=[msg, model_dropdown, history_state],
            outputs=[msg, chatbot_component]
        )

        # Остановка генерации
        stop_btn.click(fn=chatbot.stop_generation, inputs=[], outputs=[])

        # Очистка чата
        clear_btn.click(fn=chatbot.clear_chat, inputs=[], outputs=[chatbot_component])

    return demo


if __name__ == "__main__":
    demo = create_demo()
    demo.launch(server_name="0.0.0.0", server_port=7860)