import os

from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for)

app = Flask(__name__)


@app.route('/')
def index():
    # Serve the React app instead of the template
    return send_from_directory('static/react', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # Serve static files from the React build
    if os.path.exists(os.path.join(app.static_folder, 'react', path)):
        return send_from_directory('static/react', path)
    return send_from_directory('static/react', 'index.html')

@app.route('/api/hello', methods=['POST'])
def hello_api():
    name = request.json.get('name')
    if name:
        return {'message': f'Hello, {name}!'}
    return {'error': 'No name provided'}, 400

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Keep the original hello route for the template version if desired
@app.route('/hello', methods=['POST'])
def hello():
    name = request.form.get('name')

    if name:
        print('Request for hello page received with name=%s' % name)
        return render_template('hello.html', name = name)
    else:
        print('Request for hello page received with no name or blank name -- redirecting')
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)