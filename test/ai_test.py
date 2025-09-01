import ollama

response = ollama.chat(model='gemma3:270m', messages=[
    {'role': 'user', 'content': 'kahibaw ka onsa na bisaya?'}
])

print(response['message']['content'])
