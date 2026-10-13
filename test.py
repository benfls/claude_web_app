import os
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()  # Charge les variables depuis .env

client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY"))

inputs = [{"role": "user", "content": "Hello!"}]

response = client.beta.conversations.start(
    agent_id="ag_01a135ad49be778da0d7e617d8834ed8",
    agent_version=0,
    inputs=inputs,
)

print(response)