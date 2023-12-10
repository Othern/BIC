# 引入必要的套件
from flask import Flask, render_template, request, redirect, url_for,jsonify
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import uuid
import numpy as np
from scratch_url_preview import get_preview
import re

# 建立 Flask 應用程式
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'  # 設定 SECRET_KEY 以保護 session 資訊
socketio = SocketIO(app)

# 紀錄啟用中的房間及使用者列表的字典
activate_room = {}
usersList = {}
votes = {}




# 定義首頁路由及不同表單操作的功能
@app.route('/', methods=['GET', 'POST'])
def index():
    # 首頁請求分為 GET 及 POST 兩種情況處理
    if request.method == 'POST':
        # 創建文字或語音聊天室的動作
        if 'create_text' in request.form:
            room_code = uuid.uuid4().hex[:6].upper()  # 產生隨機的房間代碼
            activate_room[room_code] = []  # 建立新的房間及對應的訊息列表
            return redirect(url_for('.chat', room=room_code, type='text'))  # 導向至文字聊天頁面

        # 加入現有聊天室的動作
        elif 'join' in request.form:
            room_code = request.form.get('room_code')  # 取得使用者輸入的房間代碼
            if room_code in activate_room:  # 確認該房間是否存在
                return redirect(url_for('.chat', room=room_code, type='text'))  # 導向至文字聊天頁面
            else:
                return render_template('error_join.html', room=room_code)  # 若房間不存在，導向至錯誤頁面
    return render_template('index.html')  # 顯示首頁的 HTML

# 定義文字聊天頁面路由
@app.route('/chat_text/<room>/<type>')
def chat(room, type):
    return render_template('chat.html', room=room, type=type)  # 顯示文字聊天室的 HTML 頁面

# 處理接收訊息的功能
@socketio.on('message')
def handle_message(data):
    room = data['room']
    if room not in activate_room:
        activate_room[room] = []
    activate_room[room].append(data)

    # 使用正規表達式搜尋第一個網址
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    match = url_pattern.search(data['msg'])
    
    if match:
        first_url = match.group()
        
        data['link'] = first_url
        data.update(get_preview(first_url))
    send(data, room=room)

@app.route('/joinTextChat', methods=['POST'])    
def join_chat():
    uid = str(uuid.uuid4().hex[:6])
    data = request.json
    username = data['username']
    room = data['room']
    if room not in usersList:
        usersList[room] = []

    user_info = {'username': username, 'uid': uid}
    usersList[room].append(user_info)
    
    return jsonify({'username': username,'room': room ,'uid':uid})

# 處理使用者加入聊天室的功能
@socketio.on('text_join')
def on_join(data):
    username = data['username']
    room = data['room']

    if room in activate_room:
        for msg in activate_room[room]:
            emit('message', msg)

    for i,d in enumerate(usersList[room]):
        if d['username'] == username:
            usersList[room][i]['sid']= request.sid
            break
    join_room(room)
    send({'msg': username + ' has entered the room.', 'user': 'System'}, room=room)

    
### 投票功能 ###
@app.route('/create_vote', methods=['POST'])
def create_vote():
    data = request.json
    vote_id = str(uuid.uuid4())  # 生成唯一代號
    # 初始化每個選項的投票計數為0
    option_counts = np.zeros(len(data['options']),dtype=int)
    temp = {
        'room': data['room'],
        'title': data['title'],
        'options': data['options'],
        'multipleChoice': data['multipleChoice'],
        'counts': option_counts.tolist() 
    }
    votes[vote_id] = temp
    socketio.emit('vote_create', {'vote_id': vote_id, 'title': data['title'],'multipleChoice': data['multipleChoice'], 'options': data['options']}, room=data["room"])
    return jsonify({'vote_id': vote_id, 'title': data['title'],'multipleChoice': data['multipleChoice'], 'options': data['options']})

@app.route('/submit_vote', methods=['POST'])
def submit_vote():
    data = request.json
    vote_id = data['vote_id']
    room = data['room']
    option_index = [int(index) for index in data['option_index']]  # 從前端獲取選項索引
    if vote_id in votes:
        vote_data = votes[vote_id]
        if "counts" in vote_data:
            for index in option_index:
                vote_data["counts"][index] += 1  # 更新計數
            # 使用 SocketIO 發送最新的計數結果
            socketio.emit('vote_counts_update', {'vote_id': vote_id,'titles': vote_data['title'] ,'options':vote_data['options'] ,'counts': vote_data["counts"]}, room=room)
            
            return jsonify({'message': '投票成功', 'options':vote_data['options'] ,'counts': vote_data["counts"],'title': vote_data['title']})
        else:
            return jsonify({'message': '計數數據不存在'}), 404
    else:
        return jsonify({'message': '投票ID不存在'}), 404

@app.route('/get_votes', methods=['POST'])
def get_votes():
    data = request.json
    room = data['room']
    # 返回所有投票資訊
    vote_data = {}
    if not votes:
        for key,val in zip(votes.keys(),votes.values()):
            if val['room'] == room:
                vote_data[key] = val
    return jsonify(votes)




### 井字遊戲 ###
# 增加一個用於提供使用者列表的路由
@app.route('/get_user_list', methods=['GET'])
def get_user_list():
    room = request.args.get('room')  # 從 GET 請求中獲取 room 參數
    if not room:
        return jsonify({'error': 'Missing room parameter'}), 400

    room_users = usersList.get(room, [])
    current_user = request.cookies.get('username')
    if current_user in room_users:
        room_users.remove(current_user)

    return jsonify({'users': room_users})

# 處理使用者斷線的功能
@socketio.on('disconnect')
def disconnect_user():
    for room, users in usersList.items():
        for user in users:
            if user['sid'] == request.sid:
                users.remove(user)
                user_list = [u['username'] for u in users]
                emit('update_users_list', {'users': user_list}, room=room)
                #disconnect()

            
# 接收並處理前端發送的邀請訊息
@socketio.on('send_invite')
def handle_invite(data):
    sender = data['sender']
    receiver_username = data['receiver']  # 接收者的名稱
    room = data['room']

    # 廣播給所有在 room 中的使用者
    socketio.emit('receive_invite', {'sender': sender, 'receiver': receiver_username}, room=room)

# 被拒絕邀請的事件
@socketio.on('reject_invite')
def reject_invite(data):
    sender = data['sender']  # 邀請者的名稱
    receiver = data['receiver']  # 被邀請者的名稱
    message = data['message']  # 拒絕邀請的訊息

    # 在這裡做相應的處理，例如向邀請者發送拒絕的訊息
    # 透過 socketio.emit 向邀請者發送被拒絕的訊息
    socketio.emit('invitation_rejected', {'sender': sender, 'receiver': receiver, 'message': message})

# 被接受邀請的事件
@socketio.on('accept_invite')
def accept_invite(data):
    sender = data['sender']  # 邀請者的名稱
    receiver = data['receiver']  # 被邀請者的名稱
    message = data['message']  # 接受邀請的訊息

    # 在這裡做相應的處理，例如向邀請者發送接受的訊息
    # 透過 socketio.emit 向邀請者發送被接受的訊息
    socketio.emit('invitation_accepted', {'sender': sender, 'receiver': receiver, 'message': message})


#更新遊戲資訊
@socketio.on('update_status')
def update_status(data):
    playerStatus = data['playerStatus']
    boardState = data['boardState']
    sign = data['sign']
    print(playerStatus)
    print(boardState)
    print(sign)
    socketio.emit('NewStatus',{'playerStatus' : playerStatus,'boardState': boardState,'sign':sign})
#重新開始遊戲
@socketio.on('restartGame')
def restartGame():
    socketio.emit('restart_game')

#傳送exitGame訊息到前端
@socketio.on('exitGame')
def exit_game(data):
    message = data['message']
    socketio.emit('exit_game', {'message': message})

# 處理使用者離開聊天室的功能
@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    send({'msg': username + ' has left the room.', 'user': 'System'}, room=activate_room)


# 啟動應用程式
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=4000, debug=True, allow_unsafe_werkzeug=True)
