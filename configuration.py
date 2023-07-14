import openai,os

DOCKER_ROOT_DIR = "/app/db/"

if os.path.exists(DOCKER_ROOT_DIR):
    ROOT_DIR = DOCKER_ROOT_DIR
else:
    ROOT_DIR = "/home/yves/AI/Culture/prompts-tester/data/"

try:
    openai.api_key = open("/home/yves/keys/openAIAPI", "r").read().rstrip("\n")
    HTTP_PASSWORD = open("/home/yves/keys/MindMakerHttpPassword", "r").read().rstrip("\n")
    HOSTNAME = "http://127.0.0.1:8080"
    PLAYGROUND_URL = "http://127.0.0.1:5481"
except FileNotFoundError:
    openai.api_key = open("/app/keys/openAIAPI", "r").read().rstrip("\n")
    HTTP_PASSWORD = open("/app/keys/MindMakerHttpPassword", "r").read().rstrip("\n")
    HOSTNAME = "http://agent.iv-labs.org"
    PLAYGROUND_URL = "http://agent.iv-labs.org:5481"
