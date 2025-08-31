import ollama

response = ollama.chat(model='gemma3:270m', messages=[
    {'role': 'user', 'content': ''}
])

print(response['message']['content'])
