from fastapi import FastAPI

app = FastAPI(title="AI Personal Finance API", version="0.1.0")


# Just for example, bit hands on test
@app.get("/")
def home_page():
    return "Power up your finance and investments with the AI 🚀"