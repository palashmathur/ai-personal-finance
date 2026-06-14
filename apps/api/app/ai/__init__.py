# The AI layer — all Anthropic SDK usage lives inside this package.
# Nothing outside app/ai/ imports from anthropic directly.
# Routers and services interact with the AI only through the feature modules
# (categorize.py, nl_input.py, etc.) which return plain Python objects.
