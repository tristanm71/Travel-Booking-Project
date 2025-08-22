from flask import Flask, render_template, redirect, request, url_for, flash, get_flashed_messages
from dotenv import load_dotenv
import os 
from flask_bootstrap import Bootstrap5
from datetime import datetime
from sqlalchemy import ForeignKey, String, Integer, DateTime, JSON, Float
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, UserMixin, current_user, login_required
import requests_cache
from datetime import datetime
import requests
import json

base_url = 'https://www.skyscanner.com' #for itinerary link

load_dotenv() #load in env file

session = requests_cache.CachedSession('api_cache') #to use a cache for api requests

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
    arrival_lon: Mapped[float] = mapped_column(Float, nullable=False)
    arrival_lat: Mapped[float] = mapped_column(Float, nullable=False)
    destination_lon: Mapped[float] = mapped_column(Float, nullable=False)
    destination_lat: Mapped[float] = mapped_column(Float, nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    travelers: Mapped[int] = mapped_column(Integer, nullable=False)
    cabin_class: Mapped[str] = mapped_column(String(50), nullable=False)
    rooms: Mapped[int] = mapped_column(Integer, nullable=False)
    check_in_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    check_out_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    leg_id_list = mapped_column(JSON)
    agent_id_list = mapped_column(JSON)
    segment_id_list = mapped_column(JSON)
    place_id_list = mapped_column(JSON)
    itinerary_id_list = mapped_column(JSON)
    itinerary_id: Mapped[str] = mapped_column(String)
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    user = relationship("User", back_populates="trips")


with app.app_context():
    db.create_all()

#user authentication
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

#format time for itinerary
@app.template_filter("format_time")
def format_time(value):
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
    elif isinstance(value, datetime):
        dt = value
    else:
        return ""
    return dt.strftime("%I:%M %p")

#format date
@app.template_filter("format_date")
def format_date(value):
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
    elif isinstance(value, datetime):
        dt = value
    else:
        return ""
    return dt.strftime("%m/%d/%Y")

#home page
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
        #get the user in the data base to check if there is already a user
        user = db.session.execute(db.select(User).where(User.email == email))
        user = user.scalar()
        if user:
            flash("Email is already in use")
            return redirect(url_for("register"))
        #check username
        user = db.session.execute(db.select(User).where(User.username == username))
        user = user.scalar()
        if user:
            flash("Username is already in use")
            return redirect(url_for("register"))
        
        #once validated, make new user object and put in database
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
        #validate user login
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
        #for user auth
        login_user(user)
        return redirect(url_for('home'))
    
    return render_template("login.html", logged_in=current_user.is_authenticated)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

#use api to get the iata code of the city
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

#use iata code to search for airports
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
        #check if the user is not logged in
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

        #use fuction api to get the actual city
        destination_city = get_city(destination=destination)
        destination_city = destination_city.json()

        if len(destination_city) < 1:
            flash("Destination city does not exist")
            return redirect(url_for("home"))
        #get city
        arrival_city = get_city(destination=arrival)
        arrival_city = arrival_city.json()

        if len(arrival_city) < 1:
            flash("Arrival city does not exist")
            return redirect(url_for("home"))
        
        #find destination airports
        destination_longitude = destination_city[0]["longitude"]
        destination_latitude = destination_city[0]["latitude"]
        
        #fetch airports and check if airport exists
        destination_airports = get_airports(longitude=destination_longitude, latitude=destination_latitude)

        if destination_airports.status_code != 200:
            print("error")
            get_token()
            
            destination_airports = get_airports(longitude=destination_longitude, latitude=destination_latitude)
            destination_airports = destination_airports.json()
        else: 
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
        else:
            arrival_airports = arrival_airports.json()

        if len(arrival_airports["data"]) < 1:
            flash("No airports found from arrival city")
            return redirect(url_for("home"))
        
        travelers = request.form.get("travelers")
        #create new trip object
        new_trip = Trip(start_date=start_date, end_date=end_date, travelers=travelers, cabin_class="", 
                        rooms=0, arrival="", destination="", user=current_user, arrival_lat=arrival_latitude, 
                        arrival_lon=arrival_longitude,destination_lon=destination_longitude, 
                        destination_lat=destination_latitude, itinerary_id="")
        db.session.add(new_trip)
        db.session.commit()
        trip_id = new_trip.id #pass the id to the next page
        
        return render_template("search.html", arrival=arrival_airports["data"], destination=destination_airports["data"], logged_in=current_user.is_authenticated, trip_id=trip_id)
    
    if current_user.is_anonymous:
        flash("Please login or signup before searching")
        return redirect(url_for("login"))
    
    return redirect(url_for("home"))

@app.route("/find-tickets", methods=["POST", "GET"])
def find_tickets():
    if request.method == "POST":
        #get form variables
        arrival_airport = request.form.get("arrival")
        destination_airport = request.form.get("destination")
        cabin_class = request.form.get("cabin_class")
        trip_id = request.form.get('id')

        #find trip in the database 
        trip = db.session.execute(db.select(Trip).where(Trip.id == trip_id))
        trip = trip.scalar()
        #update values
        trip.arrival = arrival_airport
        trip.destination = destination_airport
        trip.cabin_class = cabin_class

        #fix the date bug, format the dates 
        format = "%Y-%m-%d"
        start_date = trip.start_date.strftime(format)
        end_date = trip.end_date.strftime(format)
    
        db.session.commit()
        #url to search for flight prices
        url = f"https://api.flightapi.io/roundtrip/{os.environ.get('FLIGHT_API_KEY')}/{arrival_airport}/{destination_airport}/{start_date}/{end_date}/{trip.travelers}/0/0/{trip.cabin_class}/USD"
        # print(url)
        tickets = session.get(url)
        #check if there is flights, else send user back to home page
        options = tickets.json()
        try:
            itineraries = options["itineraries"]
        except:
            flash("API key error")
            print(options)
            return redirect(url_for("home"))

        if len(options) < 1:
            flash("No flights found")
            return redirect(url_for("home"))
        
        # filename = 'tickets.json'
        # with open(filename, "w") as json_file:
        #     json.dump(options, json_file, indent=4)
        # print(options)
        
        #format prep to display
        itinerary_list = []
        leg_id_list = {}
        agent_id_list = {}
        segment_id_list = {}
        place_id_list = {}
        itinerary_id_list = {}

        #make hash tables for different sections that need to be accessed to reduce time
        for leg in options["legs"]:
            leg_id_list[leg["id"]] = leg

        for agent in options["agents"]:
            agent_id_list[agent["id"]] = agent

        for segment in options["segments"]:
            segment_id_list[segment["id"]] = segment

        for place in options["places"]:
            place_id_list[place["id"]] = place

        trip.leg_id_list = leg_id_list
        trip.agent_id_list = agent_id_list
        trip.segment_id_list = segment_id_list
        trip.place_id_list = place_id_list
        db.session.commit()

        #loop through the itinerary and format it for the html page
        for option in options["itineraries"]:
            #the id is the key, the option json is the val
            itinerary_id_list[option["id"]] = option
            itinerary = {
                "id": "",
                "leg1_departure": "",
                "leg1_arrival": "",
                "leg1_duration": 0,
                "leg1_stop_count": 0,
                "leg1_layover_list": [],
                "leg2_departure": "",
                "leg2_arrival": "",
                "leg2_duration": 0,
                "leg2_stop_count": 0,
                "leg2_layover_list": [],
                "price": 0.0,
                "agent": "",
                "url": "https://www.skyscanner.com"
            }
            #url and id
            itinerary["url"] = itinerary["url"] + option["pricing_options"][0]["items"][0]["url"]
            itinerary["id"] = option["id"]

            #get leg 1 data
            if leg_id_list[option["leg_ids"][0]]:
                leg = leg_id_list[option["leg_ids"][0]]
                itinerary["leg1_departure"] = leg["departure"]
                itinerary["leg1_arrival"] = leg["arrival"]
                itinerary["leg1_duration"] = int(leg["duration"])
                itinerary["leg1_stop_count"] = leg["stop_count"]
                
                #get all of the segment data and layover information
                if len(leg["segment_ids"]) > 1:
                    layovers = []
                    layover_duration = 0
                    #find the difference between a segments arrival and departure to get layover
                    for i in range(0, len(leg["segment_ids"]) - 1):
                        if segment_id_list[leg["segment_ids"][i]]:
                            segment1 = segment_id_list[leg["segment_ids"][i]]
                            segment2 = segment_id_list[leg["segment_ids"][i + 1]]
                            segment1_arrival = datetime.fromisoformat(segment1["arrival"])
                            segment2_departure = datetime.fromisoformat(segment2["departure"])
                            difference = segment2_departure - segment1_arrival
                            difference = difference.total_seconds()
                            hours = int(difference // 3600)
                            mins = int((difference % 3600) / 60)
                            layover_place = place_id_list[segment1["destination_place_id"]]["display_code"]
                            formatted_layover = f"{hours}h {mins}m layover at {layover_place}"
                            if len(layovers) > 0:
                                formatted_layover = ", " + formatted_layover
                            layovers.append(formatted_layover)
                            layover_duration += (difference / 60)
                        else:
                            flash("Server error")
                            return redirect(url_for("home"))
                    #subtract the layover time from the total trip duration
                    itinerary['leg1_duration'] -= int(layover_duration) 
                    itinerary["leg1_layover_list"] = layovers
            else:
                flash("Server error")
                return redirect(url_for("home"))

            #same thing for leg 2
            if leg_id_list[option["leg_ids"][1]]:
                leg = leg_id_list[option["leg_ids"][1]]
                itinerary["leg2_departure"] = leg["departure"]
                itinerary["leg2_arrival"] = leg["arrival"]
                itinerary["leg2_duration"] = leg["duration"]
                itinerary["leg2_stop_count"] = leg["stop_count"]

                if len(leg["segment_ids"]) > 1:
                    layovers = []
                    layover_duration = 0
                    for i in range(0, len(leg["segment_ids"]) - 1):
                        if segment_id_list[leg["segment_ids"][i]]:
                            segment1 = segment_id_list[leg["segment_ids"][i]]
                            segment2 = segment_id_list[leg["segment_ids"][i + 1]]
                            segment1_arrival = datetime.fromisoformat(segment1["arrival"])
                            segment2_departure = datetime.fromisoformat(segment2["departure"])
                            difference = segment2_departure - segment1_arrival
                            difference = difference.total_seconds()
                            hours = int(difference // 3600)
                            mins = int((difference % 3600) / 60)
                            layover_place = place_id_list[segment1["destination_place_id"]]["display_code"]
                            formatted_layover = f"{hours}h {mins}m layover at {layover_place}"
                            if len(layovers) > 0:
                                formatted_layover = ", " + formatted_layover
                            layovers.append(formatted_layover)
                            layover_duration += (difference / 60)
                        else:
                            flash("Server error")
                            return redirect(url_for("home"))

                    itinerary['leg2_duration'] -= int(layover_duration)                        
                    itinerary["leg2_layover_list"] = layovers
            else:
                flash("Server error")
                return redirect(url_for("home"))
            #price
            itinerary["price"] = option["cheapest_price"]["amount"] / trip.travelers
            
            #check if agent for flight is there
            if agent_id_list[option["pricing_options"][0]["agent_ids"][0]]:
                agent = agent_id_list[option["pricing_options"][0]["agent_ids"][0]]
                itinerary["agent"] = agent["name"]
            else:
                print("error")

            #append the entire itinerary information to the list
            itinerary_list.append(itinerary)
        trip.itinerary_id_list = itinerary_id_list
        db.session.commit()
        return render_template('tickets.html', logged_in=current_user.is_authenticated, trip=trip, url=base_url, itinerary_list=itinerary_list)
    return render_template(url_for('tickets.html'))

#search for hotels
def get_hotels(longitude, latitude):
    url = "https://api.liteapi.travel/v3.0/data/hotels"
    headers = {
        "X-API-Key": os.environ.get("LITEAPI_KEY"),
        "accept": "application/json"
    }
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "limit": 200,
        "radius": 10000
    }
    response = session.get(url, params=params, headers=headers)
    return response

#get the prices for the hotels
def get_hotel_offers(hotel_ids, check_in_date, check_out_date, occupants, iataCode):
    url = "https://api.liteapi.travel/v3.0/hotels/rates"
    headers = {
        "X-API-Key": os.environ.get("LITEAPI_KEY"),
        "accept": "application/json"
    }
    payload = {
        "guestNationality": "US",
        "checkin": check_in_date,
        "checkout": check_out_date,
        "currency": "USD", 
        "timeout": 12,
        "maxRatesPerHotel": 1,
        "limit": 200,
        "hotelIds": hotel_ids,
        "occupancies": occupants,
        "iataCode": iataCode,
        "maxRatesPerHotel": 5,
        "radius": 10000

    }
    response = session.post(url, json=payload, headers=headers)
    return response

#get hotel details
def get_hotel_details(hotel_id):
    url = "https://api.liteapi.travel/v3.0/data/hotel"
    headers = {
        "X-API-Key": os.environ.get("LITEAPI_KEY"),
        "accept": "application/json"
    }
    params = {
        "hotelId": hotel_id
    }
    response = session.get(url, params=params, headers=headers)
    return response


@app.route("/search_hotels", methods=["POST", "GET"])
def search_hotels():
    if request.method == "POST":
        trip_id = request.form.get("trip_id")
        itinerary_id = request.form.get("itinerary_id")
        #find trip in the database 
        trip = db.session.execute(db.select(Trip).where(Trip.id == trip_id))
        trip = trip.scalar()
        trip.itinerary_id = itinerary_id

        db.session.commit() #update trip info

        #search for list of hotels
        hotels = get_hotels(longitude=trip.destination_lon, latitude=trip.destination_lat)
        hotels = hotels.json()

        hotel_id_list = {}
        for hotel in hotels["data"]:
            hotel_id_list[hotel["id"]] = hotel

        #get checkin and checkout info and format
        check_in_date = datetime.fromisoformat(trip.leg_id_list[trip.itinerary_id_list[trip.itinerary_id]["leg_ids"][0]]["arrival"])
        check_out_date = datetime.fromisoformat(trip.leg_id_list[trip.itinerary_id_list[trip.itinerary_id]["leg_ids"][1]]["departure"])

        trip.check_in_date = check_in_date
        trip.check_out_date = check_out_date
        
        check_in_date = str(check_in_date.strftime("%Y-%m-%d"))
        check_out_date = str(check_out_date.strftime("%Y-%m-%d"))
        
        db.session.commit()

        #get prices for hotels
        occupants = [{"adults": trip.travelers}]
        prices = get_hotel_offers(hotel_ids=hotels["hotelIds"], check_in_date=check_in_date, 
                                  check_out_date=check_out_date, occupants=occupants,
                                  iataCode=trip.destination)
        prices = prices.json()

        prices_id_list = {}
        for price in prices["data"]:
            # print(price["hotelId"])
            prices_id_list[price["hotelId"]] = price

        # print(prices_list)
        # with open("prices.json", 'w') as json_file:
        #     json.dump(prices_list, json_file, indent=4)
        details_id_list = {}
        for id in prices_id_list:
            details = get_hotel_details(id)
            details_id_list[id] = details.json()

        hotel_information_list = []
        # 
        # print(hotel_id_list["lp32b3e"]
        # print(len(prices_id_list["lp32b3e"]))
        # print(details_id_list["lp32b3e"])
        # with open("details_id.json", 'w') as json_file:
        #     json.dump(details_id_list["lp32b3e"], json_file, indent=4)
                      
        for id in prices_id_list:
            hotel = {
                "id": "",
                "hotel_name": "",
                "hotel_city": "",
                "hotel_description": "",
                "rating": 0.0,
                "price": 0.0,
                "photo1": "",
                "photo2": "",
                "photo3": "",
                "hotel_amenities": "",
                "check_in": "",
                "check_out": "",
                "photo_list": [],
                "address": "",
                "policies": [],
                "reviews": 0
            }

            hotel["id"] = id
            hotel["hotel_name"] = hotel_id_list[id]["name"]
            hotel["hotel_description"] = hotel_id_list[id]["hotelDescription"]
            hotel["hotel_city"] = hotel_id_list[id]["city"]
            hotel["address"] = hotel_id_list[id]["address"]
            hotel["check_in"] = details_id_list[id]["data"]["checkinCheckoutTimes"]["checkin"]
            hotel["check_out"] = details_id_list[id]["data"]["checkinCheckoutTimes"]["checkout"]
            hotel["reviews"] = hotel_id_list[id]["reviewCount"]

            if hotel_id_list[id]["rating"] != 0:
                hotel["rating"] = hotel_id_list[id]["rating"]
            elif hotel_id_list[id]["stars"] != 0:
                hotel["rating"] = hotel_id_list[id]["stars"] * 2
            else:
                hotel["rating"] = 0

            hotel["price"] = prices_id_list[id]["roomTypes"][0]["rates"][0]["retailRate"]["suggestedSellingPrice"][0]["amount"]
            hotel["photo1"] = hotel_id_list[id]["main_photo"]

            try:
                hotel["hotel_amenities"] = details_id_list[id]["data"]["hotelFacilities"]
            except KeyError:
                print("key error")

            try:
                hotel["photo2"] = details_id_list[id]["data"]["hotelImages"][1]["url"]
                hotel["photo3"] = details_id_list[id]["data"]["hotelImages"][2]["url"]

                for photo in details_id_list[id]["data"]["hotelImages"]:
                    hotel["photo_list"].append(photo["url"])

                for policy in details_id_list[id]["data"]["policies"]:
                    hotel["policies"].append(policy["description"])
            except KeyError:
                print("key error")

            hotel_information_list.append(hotel)

            
    return render_template("hotels.html", logged_in=current_user.is_authenticated, hotel_information_list=hotel_information_list)

if __name__ == "__main__":
    app.run(debug=True)