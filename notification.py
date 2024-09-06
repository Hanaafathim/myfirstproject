import dataclasses
import json
from operator import not_
import random
import socket
import string

from flask import Flask, jsonify,render_template,request,redirect,url_for,flash,session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_session import Session
from passlib.hash import pbkdf2_sha256
from flask_socketio import SocketIO, emit, join_room, leave_room, send

from flask_cors import CORS
from datetime import timedelta



app = Flask(__name__)

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:hanaa@localhost:5432/postgres"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
app.config['SESSION_TYPE']='filesystem'
app.permanent_session_lifetime = timedelta(days=10)


sess = Session(app)
db = SQLAlchemy(app)




class reg(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(30),nullable=False)
    password=db.Column(db.String(30),nullable=False)
    age=db.Column(db.Integer,nullable=False)
    phone=db.Column(db.String(15))
    email=db.Column(db.String(20))

class log__in(db.Model):
    login_id=db.Column(db.Integer,primary_key=True)
    reg_id=db.Column(db.Integer,db.ForeignKey('reg.id'))
    username=db.Column(db.String(30),nullable=False)
    


class to_details(db.Model):
    to_id=db.Column(db.Integer,primary_key=True)
    reg_id=db.Column(db.Integer,db.ForeignKey('reg.id'))
    to_username=db.Column(db.String(30),nullable=False)
   

class msg_data(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    from_id=db.Column(db.Integer,db.ForeignKey('reg.id'))
    from_name=db.Column(db.String(20),nullable=False)
    to_id=db.Column(db.Integer,db.ForeignKey('reg.id'))
    to_name=db.Column(db.String(20),nullable=False)
    messege=db.Column(db.String(100))
    msg_send_time=db.Column(db.Time,nullable=False)
   
class  room(db.Model):
    room_id=db.Column(db.String(100),primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('reg.id'))


@app.route('/')
def regitration():
    return render_template('user_reg.html')

@app.route('/submit',methods=['POST'])
def register():
    if request.method=='POST':
        username = request.form['username']
        password=request.form['password']
        age=request.form['age']
        phone=request.form['phone']
        email=request.form['email']
        hash_password=pbkdf2_sha256.hash(password) 

        new_user=reg(username=username,password=hash_password,age=age,phone=phone,email=email)
        db.session.add(new_user)
        db.session.commit()
        room_id= ''.join(random.choices(string.ascii_uppercase + string.digits,k=8))
        user_id = new_user.id
        new_room=room(room_id=room_id,user_id=user_id)
        db.session.add(new_room)
        db.session.commit()
        flash('registration successsfull','success')
        return redirect(url_for('log_in'))

@app.route('/log_in')
def log_in():
    return render_template('user_login.html')

@app.route('/log_in',methods=['POST'] )
def login():

    if request.method=='POST':
        user_name=request.form['username']
        user_password=request.form['password']
        reg_record = reg.query.filter_by( username=user_name).first()
        reg_id=reg_record.id
        new_user=log__in(username=user_name,reg_id=reg_id)
       
        login_user=reg.query.filter_by(username=user_name).first()
        db.session.add(new_user)
        db.session.commit()

        if login_user and pbkdf2_sha256.verify(user_password ,login_user.password):
            session['user_id'] = login_user.id
            print("login")
            print(login_user.id)
            flash(session.get('user_id'))
            flash ('Login successfully','login')
            return redirect(url_for('chat_list'))
        else:
            flash('Invalid username and password','failed')
            return redirect(url_for('log_in'))
        

    return redirect(url_for('chat_list'))
        

        
        

@app.route('/chat_list')
def chat_list():
    user_id = session.get('user_id')
    user_name = reg.query.filter(reg.id==user_id).first()
    user_name=user_name.username
    users=reg.query.filter(reg.username!=user_name).all()
    return render_template('chat_list.html',users=users)
 

@app.route('/chat_list', methods=['POST'])
def chat_list1():
    if  request.method=='POST':
        to_name_value=request.form['button_value']
        to_user=reg.query.filter_by(username=to_name_value).first()
        reg_id=to_user.id
        session['to_name']=to_name_value
        new_user=to_details(to_username=to_name_value,reg_id=reg_id)
        db.session.add(new_user)
        db.session.commit()
        
    return redirect(url_for('personal_msg',to_name=to_name_value))

@app.route('/personal_msg')
def personal_msg():
    to_name_value=session.get('to_name')
    user_id=session.get('user_id')
    room_ = room.query.filter(room.user_id == user_id).first()
    room_id=room_.room_id
    from_= reg.query.filter_by(id=user_id).first()
    from_name=from_.username
    return render_template('personal_message.html',from_name=from_name,to_name=to_name_value,room_id=room_id)
    


    
@app.route('/api/data',methods=['GET'])
def json_data():
    user_id=session.get('user_id')
    from_reg_record = reg.query.filter_by(id=user_id).first()
    to_name=session.get('to_name')
    from_name=from_reg_record.username
    messages = msg_data.query.filter(((from_name == msg_data.from_name) & (to_name == msg_data.to_name)) |
    ((from_name == msg_data.to_name) & (to_name == msg_data.from_name))).all()
    
    message_data=[]
    for message in messages:
        message_data.append({
            'message':message.messege,
            'time':message.msg_send_time.strftime('%H:%M:%S'),
            'from':message.from_name,
            'to':message.to_name
            })
    
    return jsonify(message_data)



@socketio.on('connect')
def on_join():
    print(sess,"here")
    to_name = session.get('to_name')
    to_ = reg.query.filter_by(username=to_name).first()
    to_id = to_.id
    room_to = room.query.filter_by(user_id=to_id).first()
    room_to_code = room_to.room_id
    user_id = session.get('user_id')
    print(user_id)
    if user_id:
        room_from = room.query.filter_by(user_id=user_id).first()
        print(session)
        if room_from:
            room_from_code = room_from.room_id
            room_new_id=room_from_code+room_to_code
            join_room(room_new_id)
            print("Room joined")
        else:
            print("Room not found for user")
    else:
        print("User not logged in")
    


@socketio.on('message')
def handle_message(payload):
    print(payload)
    print("message broadcasting")
    time = datetime.now().strftime('%H:%M:%S')
    from_name = payload['username']
    from_ = reg.query.filter_by(username=from_name).first()
    from_id = from_.id
    to_name = payload['to_name']
    to_ = reg.query.filter_by(username=to_name).first()
    to_id = to_.id
    message = payload['message']
   
    room_from = room.query.filter_by(user_id=from_id).first()
    room_from_code = room_from.room_id
    room_to = room.query.filter_by(user_id=to_id).first()
    room_to_code = room_to.room_id
    room_new_to_code=room_to_code+room_from_code
    room_new_from_code=room_from_code+room_to_code
   
    if room_from_code and room_to_code:
       
        new_message = msg_data(from_id=from_id, to_id=to_id, from_name=from_name, messege=message, msg_send_time=time, to_name=to_name)
        db.session.add(new_message)
        db.session.commit()
        
        message = {
            "username": payload['username'],
            "message": payload['message'],
            "time": time,
            "reciever":payload['to_name']
        }
        
      
        send(message, broadcast=True, room=room_new_from_code)
        send(message, broadcast=True, room=room_new_to_code)



@socketio.on('disconnect')
def on_leave():
    to_name = session.get('to_name')
    to_ = reg.query.filter_by(username=to_name).first()
    to_id = to_.id
    room_to = room.query.filter_by(user_id=to_id).first()
    room_to_code = room_to.room_id
    print("server disconnected")
    user_session_id=session.get('user_id')
    room_from= room.query.filter_by(user_id=user_session_id).first()
    
    if room_from:
       room_from_code=room_from.room_id
       room_new_id=room_from_code+room_to_code
       leave_room(room_new_id)
       print('leaving room')
      
    else:
        print("room not found")
    
    


    


if __name__=='__main__':
    with app.app_context():
        app.secret_key = 'my_unique_secret_key'

        db.create_all()
    
    socketio.run(app,debug=True)




