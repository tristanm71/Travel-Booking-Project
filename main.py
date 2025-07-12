from flask import Flask, render_template, redirect, request, url_for, flash, get_flashed_messages
from dotenv import load_dotenv
import os 
from flask_bootstrap import Bootstrap5
from datetime import datetime
from sqlalchemy import ForeignKey, String, Integer, DateTime
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, UserMixin, current_user
import requests_cache
from datetime import datetime
import requests

load_dotenv()

session = requests_cache.CachedSession('api_cache')

#gathers API token for Amadeus and saves it on the env file
def get_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": f"{os.environ.get("AMADEUS_API_KEY")}",         # Replace with your actual client ID
        "client_secret": f"{os.environ.get("AMADEUS_API_SECRET")}"  # Replace with your actual client secret
    }

    response = requests.post(url, headers=headers, data=data)

    # To see the response
    print(response.status_code)
    table = response.json()
    token = table["access_token"]
    os.environ["AMADEUS_ACCESS_TOKEN"] = token


#set up flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_KEY")

#set up bootstrap styling
bootstrap = Bootstrap5(app)
 
 #for db models
class Base(DeclarativeBase):
    pass

#db set up
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
db = SQLAlchemy(model_class=Base)
db.init_app(app)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    trips = relationship("Trip", back_populates="user")

class Trip(db.Model):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arrival: Mapped[str] = mapped_column(String(100), nullable=False)
    destination: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    travelers: Mapped[int] = mapped_column(Integer, nullable=False)
    cabin_class: Mapped[str] = mapped_column(String(50), nullable=False)
    rooms: Mapped[int] = mapped_column(Integer, nullable=False)
    check_in_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    check_out_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="trips")


with app.app_context():
    db.create_all()

#user authentication
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

@app.route("/")
def home():
    today = datetime.now
    return render_template("index.html", now=today, logged_in=current_user.is_authenticated)

#register user with validation
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        username = request.form.get("username")
        user = db.session.execute(db.select(User).where(User.email == email))
        user = user.scalar()
        if user:
            flash("Email is already in use")
            return redirect(url_for("register"))
        
        user = db.session.execute(db.select(User).where(User.username == username))
        user = user.scalar()
        if user:
            flash("Username is already in use")
            return redirect(url_for("register"))
        
        new_user = User(email=email,
                        password=generate_password_hash(password, method="pbkdf2:sha256", salt_length=8),
                        username=username)
        
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("home"))
    
    return render_template("register.html", logged_in=current_user.is_authenticated)

#login user with validation
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = db.session.execute(db.select(User).where(User.username == username))
        user = user.scalar()
        if not user:
            user = db.session.execute(db.select(User).where(User.email == username))
            user = user.scalar()
            if not user:
                flash("Wrong username or email")
                return redirect(url_for('login'))
            
        if not check_password_hash(user.password, password):
            flash("Wrong password")
            return redirect(url_for('login'))
        
        login_user(user)
        return redirect(url_for('home'))
    
    return render_template("login.html", logged_in=current_user.is_authenticated)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def get_city(destination):
    url = "https://api.api-ninjas.com/v1/city"
    headers = {
        "X-Api-Key": os.environ.get("API_NINJAS_KEY")
    }
    params = {
        "name": destination
    }
    response = session.get(url, params=params, headers=headers)
    return response

def get_airports(longitude, latitude):
    url = os.environ.get("AMADEUS_BASE_URL") + "/reference-data/locations/airports"
    headers = {
        "Authorization": f"Bearer {os.environ.get("AMADEUS_ACCESS_TOKEN")}"
    }
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "page[limit]": 5
    }
    response = session.get(url, params=params, headers=headers)
    return response
    

@app.route("/find-airport", methods=["GET", "POST"])
def find_airport():
    if request.method == "POST":
        if current_user.is_anonymous:
            flash("Please login or signup before searching")
            return redirect(url_for("login"))
        #validate start and end dates
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        
        format = "%Y-%m-%d"
        start_date = datetime.strptime(start_date, format)
        end_date = datetime.strptime(end_date, format)

        if end_date <= start_date:
            flash("End date cannot be before start date")
            return redirect(url_for("home"))
        
        #validates the city inputted by the user, while gathering its location
        arrival = request.form.get("arrival")
        destination = request.form.get("destination")

        destination_city = get_city(destination=destination)
        destination_city = destination_city.json()

        if len(destination_city) < 1:
            flash("Destination city does not exist")
            return redirect(url_for("home"))
        
        arrival_city = get_city(destination=arrival)
        arrival_city = arrival_city.json()

        if len(arrival_city) < 1:
            flash("Arrival city does not exist")
            return redirect(url_for("home"))
        
        #find destination airports
        destination_longitude = destination_city[0]["longitude"]
        destination_latitude = destination_city[0]["latitude"]

        destination_airports = get_airports(longitude=destination_longitude, latitude=destination_latitude)

        if destination_airports.status_code != 200:
            print("error")
            get_token()
            
        destination_airports = get_airports(longitude=destination_longitude, latitude=destination_latitude)
        destination_airports = destination_airports.json()

        if len(destination_airports["data"]) < 1:
            flash("No airports found from destination city")
            return redirect(url_for("home"))

        #arrival airports
        arrival_longitude = arrival_city[0]["longitude"]
        arrival_latitude = arrival_city[0]["latitude"]

        arrival_airports = get_airports(longitude=arrival_longitude, latitude=arrival_latitude)

        if arrival_airports.status_code != 200:
            print("error")
            get_token()
        
        arrival_airports = get_airports(longitude=arrival_longitude, latitude=arrival_latitude)
        arrival_airports = arrival_airports.json()

        if len(arrival_airports["data"]) < 1:
            flash("No airports found from arrival city")
            return redirect(url_for("home"))

        print(arrival_airports["data"][0])
        print(destination_airports["data"][0])
        return render_template("search.html", arrival=arrival_airports["data"], destination=destination_airports["data"])
    
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)