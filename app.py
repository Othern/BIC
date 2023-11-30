from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
activate_room = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'create_text' in request.form:
            # 生成唯一的房间代码
            room_code = uuid.uuid4().hex[:6].upper()
            activate_room[room_code] = []
            return redirect(url_for('.chat', room=room_code,type='text'))
        elif 'create_voice' in request.form:
            # 生成唯一的房间代码
            room_code = uuid.uuid4().hex[:6].upper()
            activate_room[room_code] = []
            return redirect(url_for('.chat', room=room_code,type='voice'))

        elif 'join' in request.form:
            # 加入已有的房间
            room_code = request.form.get('room_code')
            if room_code in activate_room:   
                return redirect(url_for('.chat', room=room_code,type='text'))
            else:
                return render_template('error_join.html',room=room_code)
    return render_template('index.html')

@app.route('/chat_text/<room>/<type>')
def chat(room,type):
    return render_template('chat.html', room=room,type=type)

@socketio.on('message')
def handle_message(data):
    room = data['room']
    # 存储消息
    if room not in activate_room:
        activate_room[room] = []
    activate_room[room].append(data)

    send(data, room=room)

@socketio.on('text_join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    # 发送旧消息给刚加入的用户
    if room in activate_room:
        for msg in activate_room[room]:
            emit('message', msg)

    send({'msg': username + ' has entered the room.', 'user': 'System'}, room=room)
    

@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    send({'msg': username + ' has left the room.', 'user': 'System'}, room=room)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=4000, debug=True ,allow_unsafe_werkzeug=True)
