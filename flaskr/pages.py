from flask import Flask, render_template, request, flash, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from flaskr import backend
from google.cloud import storage
import os
import uuid
import zipfile
from flaskext.markdown import Markdown


def make_endpoints(app):
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.session_protection = 'strong' 
    Markdown(app)       

    class User(UserMixin):
        def __init__(self, name):
            #!!!!!!! DOESNT DISPLAY FULL NAME
            self.name = f'{name}'
            self.id = f'{uuid.uuid4()}'

        def get_id(self):
            return self.id

        def is_authenticated(self):
            return True
        
        def is_active(self):
            return True

        def is_anonymous(self):
            return False

    @login_manager.user_loader
    def load_user(name):
        user = User(name)
        return user
    
    @app.route('/')
    # @app.route('/main')
    def home():
        return render_template("main.html")

    @app.route('/pages')
    def pages():
        be = backend.Backend(app)
        page_names = be.get_all_page_names()
        return render_template('pages.html', page_names=page_names)

    @app.route('/pages/<sub_page>')
    def pages_next(sub_page):
        be = backend.Backend(app)
        md_content = be.get_wiki_page(sub_page)
        return render_template(f'{sub_page}.html', md_content=md_content)

    @app.route('/about')
    def about():
        return render_template('about.html')
    
    @app.route('/welcome')
    @login_required
    def welcome():
        return render_template('welcome.html')
        

    @app.route('/login', methods=['GET'])
    def get_login():
        return render_template('login.html')

    @app.route('/auth_login', methods=['POST'])
    def auth_login():

        user_check = {
            'username' : request.form.get('Username'),
            'password' : request.form.get('Password')
        }

        be = backend.Backend(app)
        valid, data = be.sign_in(user_check)
        
        if not valid:
            return render_template('login.html', error='Incorret Username and/or Password')
        
        user = load_user(data)
        login_user(user)

        return redirect(url_for('welcome'))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect('/')

    @app.route('/upload', methods=['GET','POST'])
    @login_required
    def upload(): #TODO doesn't properly route to the user's system #TODO A user can overwrite a pre-existing markdown, some check needs to be created when uploading
        if request.method == 'POST':
            file = request.files['image']
            filename = os.path.basename(file.filename)
            #gets directory from the cloud as opposed to your system, no idea why
            directory = os.path.abspath(file.filename)
            #what the directory looks like in console
            print("\n\n\n\n")
            print(filename)
            print(directory)
            print("\n\n\n")
            if filename.endswith('.jpg') or filename.endswith('.jpeg') or filename.endswith('.png'):# or filename.endswith('.md')
                file.save(f"images/%s" % directory)
                image = open(f"images/%s" % directory, "rb")
                be = backend.Backend(app)
                be.upload(image)
                image.close()
                os.remove("images/%s" % directory)
            elif filename.endswith('.zip'):
                with zipfile.ZipFile(directory, 'r') as z:
                    for zipped_image in z.namelist():
                        if zipped_image.endswith('.jpg') or zipped_image.endswith('.jpeg') or zipped_image.endswith('.png'):
                            file.save(f"images/%s" % zipped_image)
                            image = open(f"images/%s" % zipped_image, "rb")
                            be = backend.Backend(app)
                            be.upload(image)
                            image.close()
                            os.remove("images/%s" % zipped_image)
            else:
                render_template('upload.html', error='Incorret File Type')
            
            
            return redirect(url_for("home"))

        return render_template('upload.html')


    @app.route('/signup', methods=['GET'])
    def get_signup():
        return render_template('signup.html')

    @app.route('/auth_signup', methods=['POST'])
    def sign_up():
        
        new_user = {
            'name'     : request.form.get('Name'),
            'username' : request.form.get('Username'),
            'password' : request.form.get('Password')
        }

        be = backend.Backend(app)
        valid, data = be.sign_up(new_user)

        if not valid:
            return render_template('signup.html', error='User already exists')
        
        user = load_user(data)
        login_user(user)

        return redirect(url_for('welcome'))

    @app.errorhandler(405)
    def invalid_method(error):
        flash('Incorrect method used, try again')
        return redirect(url_for('/')), 405

    """
    {% with messages = get_flashed_messages() %}
        {% if messages %}
            <ul class=flashes>
            {% for message in messages %}
                <li>{{ message }}</li>
            {% endfor %}
            </ul>
        {% endif %}
    {% endwith %}
    """