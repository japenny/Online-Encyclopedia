from google.cloud import storage
from flask import Flask, render_template, redirect, request, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
#Hasing password
import bcrypt #gensalt, hashpw, checkpw
import base64
import hashlib
import os

# TODO(Project 1): Implement Backend according to the requirements.
class Backend:
    
    def __init__(self, app):
        #Used for logging in/out
        test_app = Flask(__name__)
        self.login_manager = LoginManager()
        self.login_manager.init_app(test_app)
        #Buckets
        storage_client = storage.Client()
        self.bucket_content = storage_client.bucket('minorbugs_content')
        self.bucket_users = storage_client.bucket('minorbugs_users')
    
    def get_wiki_page(self, name):
        raise NotImplementedError

    def get_all_page_names(self):
        raise NotImplementedError

    def upload(self, content):
        storage_client = storage.Client()
        bucket = storage_client.bucket('minorbugs_content')
        print(os.path.basename(content.name))
        blob = bucket.blob(os.path.basename(content.name))
        blob.upload_from_file(content)
        return True
            
    def get_image(self):
        raise NotImplementedError
    

    def sign_up(self, user_info):
        user_name = user_info['username'].lower()
        user_blob = self.bucket_users.blob(f'{user_name}')

        if user_blob.exists():
            return False, tuple()

        user_pass = user_info['password']
        name = user_info['name']

        mixed = f'{user_pass}hi{user_name}'
        encoded = base64.b64encode(hashlib.sha256(mixed.encode()).digest())
        salt = bcrypt.gensalt()
        hash_pass = bcrypt.hashpw(encoded, salt)
        print(f'---------------------------------------------------------{hash_pass}-----------------------------')

        user_blob.upload_from_string(f"{name}\n{hash_pass}")
        return True, (user_name, name)


    def sign_in(self, user_check):
        user_name = user_check['username'].lower()
        user_blob = self.bucket_users.blob(f'{user_name}')
        
        print('---------------------------------------------------1---------------------------------------------------------------------')

        if not user_blob.exists():
            return False, tuple()
        
        print('---------------------------------------------------2---------------------------------------------------------------------')

        content = user_blob.download_as_string().split('\n')
        name = content[0]
        hash_pass = content[1]

        user_pass = user_check['password']
        mixed = f'{user_pass}hi{user_name}'
        encoded = base64.b64encode(hashlib.sha256(mixed.encode()).digest())
        
        if not bcrypt.checkpw(encoded, hash_pass):
            return False, tuple()

        return True, (user_name, name)
        
    def get_image(self):
        raise NotImplementedError


"""
    #Sign up
    user_name = user_info['username']
    user_blob = self.bucket_content.blob(f"{user_name}.txt' ")

    if user_blob.exists():
        return (False,)

    name = user_info['name']
    user_pass = user_info['username']

    encoded = base64.b64encode(hashlib.sha256(user_pass.encode()).digest()
    salt = bcrypt.gensalt()
    hash_pass = hashpw(encoded, salt)

    user_blob.upload_from_string(f"{name}\n{hash_pass}")
    return (True, user_name)



    #Writing to file
    def write(self, bucket_name, blob_name, content):
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)

            with blob.open('w') as w:
                w.write()

            raise NotImplementedError
"""
