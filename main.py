from flask import Flask, render_template, redirect
from dotenv import load_dotenv
import os 
from flask_bootstrap import Bootstrap5

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_KEY")

bootstrap = Bootstrap5(app)

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)