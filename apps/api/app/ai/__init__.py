# The AI layer — all LLM usage lives inside this package.
# Nothing outside app/ai/ talks to an LLM provider directly. The get_llm()
# factory (llm.py) is the only place that knows which provider/model is used, so
# the rest of the app stays provider-agnostic. Routers and services interact with
# the AI only through the feature modules (categorize.py, nl_input.py, etc.),
# which return plain Python objects.
