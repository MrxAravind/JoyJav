import time
from flask import Flask
from threading import Thread
from datetime import datetime


app = Flask('')

@app.route('/')
def home():
    return f"I'm Alive... Fuck Off {datetime.now()}"


@app.route('/logs')
def logs():
    try:
        log_filename = "Jav.log"
        with open(log_filename, 'r') as f:
            log_content = f.read().replace('\n', '<br>')
        return f"<pre>{log_content}</pre>"
    except Exception as e:
        logging.error(f"Error in logs route: {e}")
        return "<center><h1>Error Occurred</h1></center>"
        


def run():
  app.run(host='0.0.0.0',port=80)

def keep_alive():  
    t = Thread(target=run)
    t.start()


