import urllib.request
import os

# Create folders
os.makedirs('static/css/fonts', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

files = [
    (
        '[cdnjs.cloudflare.com](https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css)',
        'static/css/bootstrap.min.css'
    ),
    (
        '[cdnjs.cloudflare.com](https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/js/bootstrap.bundle.min.js)',
        'static/js/bootstrap.bundle.min.js'
    ),
    (
        '[cdnjs.cloudflare.com](https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.11.0/font/bootstrap-icons.min.css)',
        'static/css/bootstrap-icons.css'
    ),
    (
        '[cdnjs.cloudflare.com](https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.11.0/font/fonts/bootstrap-icons.woff2)',
        'static/css/fonts/bootstrap-icons.woff2'
    ),
    (
        '[cdnjs.cloudflare.com](https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.11.0/font/fonts/bootstrap-icons.woff)',
        'static/css/fonts/bootstrap-icons.woff'
    ),
]

for url, path in files:
    print(f'Downloading {path}...')
    urllib.request.urlretrieve(url, path)
    print(f'Done!')

print('All files downloaded successfully!')
