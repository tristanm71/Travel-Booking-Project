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

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_KEY")

bootstrap = Bootstrap5(app)
 
class Base(DeclarativeBase):
    pass

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

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

@app.route("/")
def home():
    today = datetime.now
    return render_template("index.html", now=today, logged_in=current_user.is_authenticated)


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


if __name__ == "__main__":
    app.run(debug=True)