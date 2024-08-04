from flask import Flask, render_template, redirect, url_for, request, flash, send_file, abort
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from werkzeug.utils import secure_filename
import os
from wtforms import StringField, SubmitField, SelectField, TimeField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, URL
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from facts import facts
import random

# imports to save data to sheets
import csv
import requests


rating_options = ['🤬', '😢😢', '😊😊😊', '😃😃😃😃', '🤩🤩🤩🤩🤩']

app = Flask(__name__)
app.config['SECRET_KEY'] = 'my_secret_key_is_kept_in_my___'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cifi_cafes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = './uploaded_image_files'  # Change this to your desired upload folder
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Specify your Sheety API endpoint URL
sheety_api_url = os.environ.get('SHEETY_API_URL')

class Cafe(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    cafe_name = db.Column(db.String(250), nullable=False)
    opening_time = db.Column(db.Time)
    closing_time = db.Column(db.Time)
    coffee_rating = db.Column(db.Integer, nullable=False)
    wifi_rating = db.Column(db.Integer, nullable=False)
    toilet_rating = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(250))


# Image Model
class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cafe_id = db.Column(db.Integer, db.ForeignKey('cafe.id'), nullable=False)
    filename = db.Column(db.String(100), nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    password = db.Column(db.String(100))
    status = db.Column(db.String(12))


db.create_all()

# Create the first admin
admin = User(email="ishanrastogi26@gmail.com", password="i9s19h8a1n14", status="super-admin")
db.session.add(admin)
db.session.commit()


# DEFINE WTF FORMS


class CifiForm(FlaskForm):
    cafe_name = StringField("Cafe Name", validators=[DataRequired()])
    opening_time = TimeField('Opening Time')
    closing_time = TimeField('Closing Time')
    coffee_rating = SelectField('Coffee Rating', choices=rating_options, validators=[DataRequired()])
    wifi_rating = SelectField('Wifi Rating', choices=rating_options, validators=[DataRequired()])
    toilet_rating = SelectField('Toilet Rating', choices=rating_options, validators=[DataRequired()])
    location = StringField('Location', validators=[DataRequired(), URL()])
    images = FileField('Upload Images', validators=[DataRequired(), FileAllowed(['jpg', 'png'], 'Images only!')],
                       render_kw={"multiple": True})
    submit = SubmitField('Add Cafe')


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log Me In")


class JoinJuryForm(FlaskForm):
    email = StringField('Email')
    password = PasswordField('Password')
    reason = TextAreaField('Why should we HIRE YOU?', render_kw={'placeholder': 'Enter your reason here'})
    submit = SubmitField('Join the Jury')


# UTILITY FUNCTIONS


def set_status():
    if current_user.is_authenticated:
        return current_user.status
    else:
        return "user"


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # print(current_user.is_authenticated)
        if not current_user.is_authenticated:
            return redirect(url_for('home'))
        elif (current_user.status != "admin") and (current_user.status != "super-admin"):
            # return abort(403)
            print("Redirecting to Home")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function


def save_to_csv(email, password, reason):
    with open('join_jury_req.csv', 'a', newline='') as csvfile:
        fieldnames = ['Email', 'Password', 'Reason']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Check if the file is empty, if yes, write the header
        if csvfile.tell() == 0:
            writer.writeheader()

        # Write the data
        writer.writerow({'Email': email, 'Password': password, 'Reason': reason})


@login_manager.user_loader
def load_user(user_id):
    # Implement logic to load a user object using the user_id
    return User.query.get(user_id)


# REQUEST LISTENERS


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = User.query.filter_by(email=email).first()
        # Email doesn't exist or password incorrect.
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        elif password != user.password:
            flash("Password Doesn't Match")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('home'))
    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/')
def home():
    cafe_list = db.session.query(Cafe).all()
    leng = len(cafe_list)
    user_stat = set_status()
    fact_list = []
    for i in range(3):
        fact_list.append(random.choice(facts))
    return render_template('index.html', cafes=cafe_list, leng=leng, path="/", user_stat=user_stat, fact_list=fact_list)


@app.route('/insert-new-cafe', methods=["GET", "POST"])
@admin_only
def insert_new():
    form = CifiForm()
    if form.validate_on_submit():
        # print("Entered Form Validation")
        # images = form.images.data
        images = request.files.getlist('images')
        new_cafe = Cafe(
            cafe_name=form.cafe_name.data, opening_time=form.opening_time.data,
            closing_time=form.closing_time.data, coffee_rating=form.coffee_rating.data,
            wifi_rating=form.wifi_rating.data, toilet_rating=form.toilet_rating.data,
            location=form.location.data
        )

        # print("Created Object Form Data")
        db.session.add(new_cafe)
        db.session.commit()

        for image in images:
            if image:
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))  # Save image to a folder
                new_image = Image(cafe_id=new_cafe.id, filename=filename)
                db.session.add(new_image)
        db.session.commit()

        # print("New Cafe Inserted")
        return redirect(url_for('home'))
    user_stat = set_status()
    return render_template('new-cafe.html', form=form, path='/insert-new-cafe', user_stat=user_stat)


@app.route('/cafe/<id>')
def cafe_details(id):
    cafe_to_show = Cafe.query.get(id)
    cafe_images = Image.query.filter_by(cafe_id=cafe_to_show.id).all()
    image_urls = [url_for('uploaded_images', filename=image.filename) for image in cafe_images]
    user_stat = set_status()

    return render_template('cafe-details.html', cafe=cafe_to_show, user_stat=user_stat, image_urls=image_urls)


@app.route('/uploads/<filename>')
def uploaded_images(filename):
    # return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))


@app.route('/delete/<id>', methods=["POST"])
@admin_only
def delete_cafe(id):
    if request.method == 'POST':
        cafe_to_del = Cafe.query.get(id)
        db.session.delete(cafe_to_del)
        db.session.commit()
    return redirect('/')


@app.route('/joinjury', methods=['GET','POST'])
def index():
    form = JoinJuryForm()
    if form.validate_on_submit():
        # Process the form data (You can save to a database, authenticate, etc.)
        email = form.email.data
        password = form.password.data
        reason = form.reason.data

        # Add data to a local CSV File
        save_to_csv(email, password, reason)
        print('Successfully Added to Local CSV File!')

        # Add data to Google Sheet
        # Prepare data to be sent to Sheety API
        data = {
            "sheet1": {
                "email": email,
                "password": password,
                "reason": reason
            }
        }
        # Make a POST request to Sheety API endpoint
        response = requests.post(sheety_api_url, json=data)

        # Check the response status
        if response.status_code == 200:
            print("Data successfully saved to Google Sheets.")
        else:
            print(f"Error: {response.status_code}, {response.text}")

        # Reroute to Home Page after success
        return redirect(url_for('home'))

    return render_template('joinjury.html', form=form)


if __name__ == '__main__':
    app.run(debug=True)
